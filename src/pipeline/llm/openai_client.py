"""Cliente OpenAI deterministico, com cache e guard-rail de orcamento (F5.2, D8, D9).

- temperature=0, seed do .env, response_format json_schema strict.
- Retentativa com backoff exponencial (tenacity) so para 429 e 5xx.
- Cache em disco: .cache/<sha256(prompt+modelo+seed)>.json. Acerto de cache
  nao conta no orcamento.
- Orcamento global persistido em .cache/orcamento_llm.json, para valer entre
  execucoes do script. Aborta antes de chamar se MAX_LLM_CALLS ou MAX_USD
  ja foram atingidos.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import openai
import yaml
from dotenv import dotenv_values
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

from pipeline.llm.schema import response_format

RAIZ_REPO = Path(__file__).resolve().parents[3]
DIR_CACHE = RAIZ_REPO / ".cache"
ARQ_ORCAMENTO = DIR_CACHE / "orcamento_llm.json"
ARQ_PRECOS = RAIZ_REPO / "config" / "precos_llm.yaml"

MAX_TENTATIVAS = 6
TIMEOUT_REQUISICAO_S = 120
MAX_TOKENS_SAIDA = 4096

# Conferir orcamento, chamar e registrar acontecem sob o mesmo lock: com K
# workers, sem isso ate K-1 chamadas passariam do limite. Serializa so as
# chamadas reais (acertos de cache nao entram no lock).
_LOCK_ORCAMENTO = threading.Lock()


class OrcamentoEsgotado(RuntimeError):
    pass


@dataclass
class ConfigLLM:
    api_key: str
    modelo: str
    seed: int
    max_chamadas: int
    max_usd: float

    @classmethod
    def do_env(cls, arquivo: Path = RAIZ_REPO / ".env") -> "ConfigLLM":
        # dotenv_values nao injeta nada em os.environ: a chave nao vaza para os
        # subprocessos do Juice Shop. Variavel exportada no shell tem prioridade.
        valores = {**dotenv_values(arquivo), **{k: v for k, v in os.environ.items()
                                                 if k.startswith(("OPENAI_", "MAX_"))}}
        chave = valores.get("OPENAI_API_KEY") or ""
        if not chave or chave.startswith("<"):
            raise RuntimeError("OPENAI_API_KEY ausente no .env (veja .env.example)")
        return cls(
            api_key=chave,
            modelo=valores.get("OPENAI_MODEL") or "gpt-4.1-mini",
            seed=int(valores.get("OPENAI_SEED") or 42),
            max_chamadas=int(valores.get("MAX_LLM_CALLS") or 400),
            max_usd=float(valores.get("MAX_USD") or 25),
        )


@dataclass
class RespostaLLM:
    conteudo: str | None       # JSON devolvido pelo modelo (None se recusou)
    recusa: str | None
    finish_reason: str | None
    modelo: str                # modelo efetivo devolvido pela API
    system_fingerprint: str | None
    seed: int
    tokens_entrada: int
    tokens_saida: int
    latencia_s: float
    custo_usd: float
    hash_prompt: str
    do_cache: bool = False

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


class ClienteLLM:
    def __init__(self, cfg: ConfigLLM):
        self.cfg = cfg
        _precos(cfg.modelo)  # falha cedo se nao houver preco
        # max_retries=0: quem controla retentativa e o tenacity, abaixo.
        self._api = openai.OpenAI(api_key=cfg.api_key, max_retries=0,
                                  timeout=TIMEOUT_REQUISICAO_S)
        self.orcamento = Orcamento(cfg.max_chamadas, cfg.max_usd)

    def gerar(self, mensagens: list[dict]) -> RespostaLLM:
        h = hash_prompt(mensagens, self.cfg.modelo, self.cfg.seed)
        arq_cache = DIR_CACHE / f"{h}.json"
        if arq_cache.exists():
            dados = json.loads(arq_cache.read_text(encoding="utf-8"))
            return RespostaLLM(**{**dados, "do_cache": True})

        with _LOCK_ORCAMENTO:
            self.orcamento.conferir()
            inicio = time.monotonic()
            resp = self._chamar(mensagens)
            latencia = time.monotonic() - inicio

            uso = resp.usage
            entrada = uso.prompt_tokens if uso else 0
            saida = uso.completion_tokens if uso else 0
            detalhes = getattr(uso, "prompt_tokens_details", None) if uso else None
            entrada_cache = (getattr(detalhes, "cached_tokens", 0) or 0) if detalhes else 0
            custo = _custo(resp.model, entrada, entrada_cache, saida)
            self.orcamento.registrar(custo)

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
            custo_usd=round(custo, 6),
            hash_prompt=h,
        )
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        dados = r.to_dict()
        dados.pop("do_cache")
        arq_cache.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        return r

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.InternalServerError)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(MAX_TENTATIVAS),
        reraise=True,
    )
    def _chamar(self, mensagens: list[dict]):
        return self._api.chat.completions.create(
            model=self.cfg.modelo,
            messages=mensagens,
            temperature=0,
            seed=self.cfg.seed,
            response_format=response_format(),
            max_completion_tokens=MAX_TOKENS_SAIDA,
        )
