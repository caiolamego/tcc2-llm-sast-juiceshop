"""Cliente OpenAI: cache optativo, retentativas limitadas e orçamento por envio."""
from __future__ import annotations

import hashlib
import json
import os
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import openai
import yaml
from dotenv import dotenv_values
from pipeline.etapas.e05_geracao_llm.erros import (ErroOperacionalLLM, GeracaoCancelada, classificar, atraso)

from pipeline.etapas.e05_geracao_llm.esquema import response_format

RAIZ_REPO = Path(__file__).resolve().parents[4]
DIR_CACHE = RAIZ_REPO / ".cache"
ARQ_ORCAMENTO = DIR_CACHE / "orcamento_llm.json"
ARQ_PRECOS = RAIZ_REPO / "config" / "precos_llm.yaml"

MAX_TENTATIVAS = 3
TIMEOUT_REQUISICAO_S = 120
MAX_TOKENS_SAIDA = 4096

# Conferir orcamento, chamar e registrar acontecem sob o mesmo lock: com K
# workers, sem isso ate K-1 chamadas passariam do limite. Serializa so as
# chamadas reais (acertos de cache nao entram no lock).
_LOCK_ORCAMENTO = threading.Lock()


class OrcamentoEsgotado(ErroOperacionalLLM):
    def __init__(self, mensagem, **kwargs):
        super().__init__(mensagem, categoria="orcamento", fatal=True, **kwargs)


@dataclass
class ConfigLLM:
    api_key: str = field(repr=False)
    modelo: str
    seed: int
    max_chamadas: int
    max_usd: float
    cache_llm: str = "desligado"

    def __post_init__(self):
        if self.cache_llm not in ('desligado', 'leitura-escrita'):
            raise ValueError('Cache LLM inválido')
        if type(self.max_chamadas) is not int or self.max_chamadas <= 0 or not math.isfinite(self.max_usd) or self.max_usd <= 0:
            raise ValueError('Limites OpenAI devem ser positivos e finitos')

    @classmethod
    def do_env(cls, arquivo: Path = RAIZ_REPO / ".env") -> "ConfigLLM":
        # dotenv_values nao injeta nada em os.environ: a chave nao vaza para os
        # subprocessos do Juice Shop. Variavel exportada no shell tem prioridade.
        valores = {**dotenv_values(arquivo), **{k: v for k, v in os.environ.items()
                                                 if k.startswith(("OPENAI_", "LLM_", "MAX_"))}}
        chave = valores.get("OPENAI_API_KEY") or ""
        if not chave or chave.startswith("<"):
            raise RuntimeError("OPENAI_API_KEY ausente no .env (veja .env.example)")
        from pipeline.etapas.e05_geracao_llm.provedor import politica_cache
        return cls(
            api_key=chave,
            modelo=valores.get("OPENAI_MODEL") or "gpt-4.1-mini",
            seed=int(valores.get("OPENAI_SEED") or 42),
            max_chamadas=int(valores.get("MAX_LLM_CALLS") or 400),
            max_usd=float(valores.get("MAX_USD") or 25),
            cache_llm=politica_cache(valores),
        )


@dataclass
class RespostaLLM:
    conteudo: str | None       # JSON devolvido pelo modelo (None se recusou)
    recusa: str | None
    finish_reason: str | None
    modelo: str                # modelo efetivo devolvido pela API
    system_fingerprint: str | None
    seed: int
    tokens_entrada: int | None
    tokens_saida: int | None
    latencia_s: float
    custo_usd: float | None
    hash_prompt: str
    do_cache: bool = False
    chamadas_enviadas: int = 1
    historico_transporte: list = field(default_factory=list)
    consumo_incerto: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def hash_prompt(mensagens: list[dict], modelo: str, seed: int) -> str:
    bruto = json.dumps({"mensagens": mensagens, "modelo": modelo, "seed": seed},
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _precos(modelo: str) -> dict:
    tabela = yaml.safe_load(ARQ_PRECOS.read_text(encoding="utf-8")) or {}
    for nome, preco in tabela.items():
        # A API devolve o nome com data (gpt-4.1-mini-2025-04-14).
        if modelo == nome or modelo.startswith(nome + "-"):
            return preco
    raise RuntimeError(f"Modelo {modelo} sem preco em {ARQ_PRECOS}; guard-rail MAX_USD inviavel")


def _custo(modelo: str, entrada: int, entrada_cache: int, saida: int) -> float:
    p = _precos(modelo)
    nao_cache = entrada - entrada_cache
    return (nao_cache * p["entrada"] + entrada_cache * p.get("entrada_cache", p["entrada"])
            + saida * p["saida"]) / 1_000_000


class Orcamento:
    def __init__(self, max_chamadas: int, max_usd: float, arquivo: Path = ARQ_ORCAMENTO):
        self.max_chamadas, self.max_usd, self.arquivo = max_chamadas, max_usd, arquivo

    def _ler(self) -> dict:
        if self.arquivo.exists():
            return json.loads(self.arquivo.read_text(encoding="utf-8"))
        return {"chamadas": 0, "usd": 0.0}

    def conferir(self) -> None:
        e = self._ler()
        if e["chamadas"] >= self.max_chamadas:
            raise OrcamentoEsgotado(f"MAX_LLM_CALLS atingido ({e['chamadas']}/{self.max_chamadas})")
        if e["usd"] >= self.max_usd:
            raise OrcamentoEsgotado(f"MAX_USD atingido (US$ {e['usd']:.4f}/{self.max_usd})")

    def registrar(self, custo_usd: float) -> dict:
        e = self._ler()
        e["chamadas"] += 1
        e["usd"] = round(e["usd"] + custo_usd, 6)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps(e, indent=2), encoding="utf-8")
        return e

    def finalizar(self, custo):
        e = self._ler()
        if custo is None:
            e['envios_consumo_desconhecido'] = e.get('envios_consumo_desconhecido', 0) + 1
        else:
            e['usd'] = round(e['usd'] + custo, 6)
        self.arquivo.write_text(json.dumps(e, indent=2), encoding='utf-8')

    def marcar_incerto(self):
        self.finalizar(None)


class ClienteLLM:
    def __init__(self, cfg: ConfigLLM, parar=None):
        self.cfg = cfg
        self.parar = parar or (lambda: False)
        _precos(cfg.modelo)  # falha cedo se nao houver preco
        # max_retries=0: somente o laço explícito controla as retentativas.
        self._api = openai.OpenAI(api_key=cfg.api_key, max_retries=0,
                                  timeout=TIMEOUT_REQUISICAO_S)
        self.orcamento = Orcamento(cfg.max_chamadas, cfg.max_usd)

    def gerar(self, mensagens: list[dict]) -> RespostaLLM:
        h = hash_prompt(mensagens, self.cfg.modelo, self.cfg.seed)
        arq_cache = DIR_CACHE / f"{h}.json"
        if self.cfg.cache_llm != "desligado" and arq_cache.exists():
            dados = json.loads(arq_cache.read_text(encoding="utf-8"))
            return RespostaLLM(**{**dados, "do_cache": True, "chamadas_enviadas": 0})

        with _LOCK_ORCAMENTO:
            inicio = time.monotonic()
            resp, historico, envios = self._chamar_com_recuperacao(mensagens)
            latencia = time.monotonic() - inicio

            uso = resp.usage
            entrada = uso.prompt_tokens if uso else None
            saida = uso.completion_tokens if uso else None
            detalhes = getattr(uso, "prompt_tokens_details", None) if uso else None
            entrada_cache = (getattr(detalhes, "cached_tokens", 0) or 0) if detalhes else 0
            custo = _custo(resp.model, entrada, entrada_cache, saida) if entrada is not None and saida is not None else None
            self.orcamento.finalizar(custo)

        if len(resp.choices) != 1:
            raise ErroOperacionalLLM("Resposta OpenAI sem escolha única; geração não aplicada",
                categoria="resposta_invalida", fatal=False, envios=envios, historico=historico)
        escolha = resp.choices[0]
        r = RespostaLLM(
            conteudo=escolha.message.content,
            recusa=getattr(escolha.message, "refusal", None),
            finish_reason=escolha.finish_reason,
            modelo=resp.model,
            system_fingerprint=resp.system_fingerprint,
            seed=self.cfg.seed,
            tokens_entrada=entrada,
            tokens_saida=saida,
            latencia_s=round(latencia, 3),
            custo_usd=round(custo, 6) if custo is not None else None,
            chamadas_enviadas=envios, historico_transporte=historico,
            consumo_incerto=bool(historico),
            hash_prompt=h,
        )
        if self.cfg.cache_llm != "desligado":
            DIR_CACHE.mkdir(parents=True, exist_ok=True)
            dados = r.to_dict()
            dados.pop("do_cache")
            arq_cache.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        return r

    def _chamar_com_recuperacao(self, mensagens):
        historico = []
        for envio in range(1, MAX_TENTATIVAS + 1):
            if self.parar():
                raise GeracaoCancelada("Geração cancelada antes do envio", envios=envio-1, historico=historico)
            try:
                self.orcamento.conferir()
            except OrcamentoEsgotado as exc:
                exc.envios, exc.historico = envio-1, historico
                raise
            # Todo envio consome o limite, inclusive timeout/429. O custo é reconciliado depois.
            self.orcamento.registrar(0.)
            try:
                return self._chamar(mensagens), historico, envio
            except openai.OpenAIError as exc:
                categoria, repetivel, fatal, status = classificar(exc)
                self.orcamento.marcar_incerto()
                delay = atraso(exc, envio) if repetivel and envio < MAX_TENTATIVAS else 0.
                historico.append({'envio': envio, 'categoria': categoria, 'status_http': status,
                                  'repetivel': repetivel, 'espera_s': delay})
                if not repetivel or envio == MAX_TENTATIVAS:
                    raise ErroOperacionalLLM("Falha OpenAI: " + categoria,
                        categoria=categoria, fatal=fatal, status_http=status,
                        envios=envio, historico=historico) from None
                limite = time.monotonic() + delay
                while time.monotonic() < limite:
                    if self.parar():
                        raise GeracaoCancelada("Geração cancelada durante retentativa", envios=envio, historico=historico)
                    time.sleep(min(.1, max(0., limite-time.monotonic())))

    def _chamar(self, mensagens: list[dict]):
        return self._api.chat.completions.create(
            model=self.cfg.modelo,
            messages=mensagens,
            temperature=0,
            seed=self.cfg.seed,
            response_format=response_format(),
            max_completion_tokens=MAX_TOKENS_SAIDA,
        )
