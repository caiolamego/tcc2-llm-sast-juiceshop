"""Chat Completions Colab, identidade verificada, cache e reservas entre processos."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path
import tempfile
import threading
import time
import uuid

import httpx
import openai
from pipeline.caminhos import RAIZ_REPO
from pipeline.llm.colab_protocol import read_json, sha, validar_manifesto
from pipeline.llm.openai_client import OrcamentoEsgotado
from pipeline.llm.provider import ConfigColab, ErroOperacionalLLM, GeracaoCancelada
from pipeline.llm.schema import Correcao, response_format


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def exclusive(path, parar=lambda: False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        while True:
            if parar():
                raise GeracaoCancelada('Geração cancelada antes do envio')
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                threading.Event().wait(0.05)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def detalhe_http_seguro(response):
    """Classificar somente mensagens conhecidas; nunca logar corpo/headers arbitrários."""
    try:
        payload = response.json()
        detail = payload.get('detail') if isinstance(payload, dict) else None
        known = {
            'VRAM insuficiente para esta configuração': 'servidor informou VRAM insuficiente (CUDA out of memory)',
            'Entrada + saída excedem MAX_CONTEXT_TOKENS; prompt não foi truncado': 'limite de contexto excedido',
            'Identidade científica divergente': 'identidade científica divergente',
            'Schema incompatível com o decodificador': 'schema incompatível com o decodificador',
            'Token inválido': 'token rejeitado pelo servidor',
        }
        if isinstance(detail, str) and detail in known:
            return known[detail]
    except (ValueError, UnicodeError):
        pass
    code = re.search(r'\bERR_NGROK_[0-9]{1,8}\b', response.text[:65536])
    if code:
        return 'túnel ngrok informou ' + code.group(0)
    return 'origem não identificada; confira o servidor e o túnel'


class Reservas:
    def __init__(self, raiz, limite):
        self.path, self.limite = Path(raiz)/'orcamento.json', limite

    def reservar(self, identidade, endpoint):
        with exclusive(self.path.with_suffix('.lock')):
            data = read_json(self.path) if self.path.exists() else {'schema_versao':'1.0', 'chamadas':0, 'eventos':[]}
            if type(data.get('chamadas')) is not int or data['chamadas'] != len(data.get('eventos',[])):
                raise ErroOperacionalLLM('Contador Colab inconsistente')
            if data['chamadas'] >= self.limite:
                raise OrcamentoEsgotado('MAX_LLM_CALLS atingido no contador Colab')
            ident = uuid.uuid4().hex
            data['chamadas'] += 1
            data['eventos'].append({'id':ident, 'estado':'reservada_consumo_desconhecido',
                                   'identidade':identidade, 'endpoint_sha256':endpoint})
            atomic_json(self.path, data)
            return ident

    def concluir(self, ident, estado):
        with exclusive(self.path.with_suffix('.lock')):
            data = read_json(self.path)
            event = next(e for e in data['eventos'] if e['id']==ident)
            event['estado'] = estado
            atomic_json(self.path, data)


@dataclass
class RespostaColab:
    conteudo: str | None
    recusa: str | None
    finish_reason: str | None
    modelo: str
    system_fingerprint: str | None
    seed: int
    tokens_entrada: int | None
    tokens_saida: int | None
    latencia_s: float
    hash_prompt: str
    identidade_inferencia: dict
    espera_inferencia_s: float
    requisicao_s: float
    chamadas_enviadas: int
    ambiente_inferencia: dict
    endpoint_sha256: str
    estado_geracao: str
    custo_usd: float | None = None
    custo_api_usd: float | None = None
    custo_infraestrutura_usd: float | None = None
    custo_motivo: str = 'custo_api_e_infraestrutura_colab_nao_informado'
    provedor: str = 'colab'
    do_cache: bool = False
    latencia_original_s: float | None = None

    def to_dict(self):
        return asdict(self)


class ClienteColab:
    def __init__(self, cfg: ConfigColab, parar=None, raiz_cache=None, http_client=None):
        self.cfg = cfg
        self.parar = parar or (lambda: False)
        self.root = Path(raiz_cache or RAIZ_REPO/'.cache/colab')
        self.identidade = cfg.identidade()
        self.endpoint = hashlib.sha256(cfg.base_url.encode()).hexdigest()
        self.http = http_client or httpx.Client(timeout=cfg.timeout, follow_redirects=False, trust_env=False)
        self.api = openai.OpenAI(base_url=cfg.base_url, api_key=cfg.api_key,
                                 http_client=self.http, timeout=cfg.timeout, max_retries=0)
        self.reservas = Reservas(self.root, cfg.max_chamadas)
        self.ambiente = None
        self.estado_conexao = 'não verificada'

    def conferir_conexao(self):
        if self.parar():
            raise GeracaoCancelada('Geração cancelada antes do diagnóstico')
        try:
            if self.cfg.identidade() != self.identidade:
                raise ErroOperacionalLLM('Identidade local alterada durante a execução')
            auth = {'Authorization': 'Bearer '+self.cfg.api_key}
            health = self.http.get(self.cfg.base_url[:-3]+'/health', headers=auth, timeout=min(15, self.cfg.timeout))
            if health.status_code != 200:
                raise ErroOperacionalLLM(f'Diagnóstico Colab recusado (HTTP {health.status_code})')
            body = health.json()
            manifest = validar_manifesto(body['manifest'])
            if body.get('status')!='ok' or manifest['cientifica']!=self.cfg.manifesto['cientifica']:
                raise ErroOperacionalLLM('Identidade do servidor Colab diverge do manifesto local')
            models = self.http.get(self.cfg.base_url+'/models', headers=auth, timeout=min(15, self.cfg.timeout))
            if models.status_code != 200:
                raise ErroOperacionalLLM(f'Listagem Colab recusada (HTTP {models.status_code})')
            if self.cfg.modelo not in [m['id'] for m in models.json()['data']]:
                raise ErroOperacionalLLM('Modelo configurado não está disponível no servidor Colab')
            self.ambiente = manifest['ambiente']
            self.estado_conexao = 'identidade_verificada'
            return {'provedor':'colab', 'modelo':self.cfg.modelo, 'estado':self.estado_conexao,
                    'identidade_sha256':manifest['identidade_sha256'], 'ambiente':self.ambiente,
                    'endpoint_sha256':self.endpoint}
        except ErroOperacionalLLM:
            self.estado_conexao='falhou'; raise
        except Exception:
            self.estado_conexao='falhou'
            raise ErroOperacionalLLM('Falha no diagnóstico Colab: conexão, manifesto ou resposta inválida') from None

    def _cache(self, path, key):
        if not path.exists():
            return None
        try:
            data = read_json(path)
            if data['chave']!=key or data['resposta_sha256']!=sha(data['resposta']):
                raise ValueError()
            r = RespostaColab(**data['resposta'])
            if r.identidade_inferencia!=self.identidade or r.hash_prompt!=key or r.finish_reason!='stop' or r.recusa or r.estado_geracao!='completa':
                raise ValueError()
            Correcao.model_validate_json(r.conteudo)
            r.do_cache=True; r.latencia_original_s=r.latencia_s
            r.latencia_s=0.0; r.requisicao_s=0.0; r.espera_inferencia_s=0.0; r.chamadas_enviadas=0
            return r
        except Exception:
            raise ErroOperacionalLLM('Cache Colab corrompido/incompatível; investigue a entrada antes de continuar') from None

    def gerar(self, mensagens):
        key = sha({'mensagens':mensagens, 'identidade':self.identidade, 'schema':response_format()})
        path = self.root/'respostas'/f'{key}.json'
        start = time.monotonic()
        if self.parar():
            raise GeracaoCancelada('Geração cancelada antes do envio')
        # Mesmo um cache exige reconciliação da identidade na sessão real.
        self.conferir_conexao()
        cached = self._cache(path,key)
        if cached:
            return cached
        wait_start=time.monotonic()
        with exclusive(self.root/'inferencia.lock', self.parar):
            waited = time.monotonic()-wait_start
            cached = self._cache(path,key)
            if cached:
                cached.espera_inferencia_s=round(waited,3)
                return cached
            self.conferir_conexao()
            request_seconds = 0.0
            for envio in range(1,4):
                if self.parar():
                    raise GeracaoCancelada('Geração cancelada antes do envio')
                reservation = self.reservas.reservar(sha(self.identidade),self.endpoint)
                try:
                    call_start=time.monotonic()
                    try:
                        result = self.api.chat.completions.create(
                            model=self.cfg.modelo, messages=mensagens, temperature=0, seed=self.cfg.seed,
                            response_format=response_format(), stream=False,
                            max_completion_tokens=self.cfg.max_tokens,
                            extra_headers={'X-LLM-Identity':self.cfg.manifesto['identidade_sha256']})
                    finally:
                        request_seconds += time.monotonic()-call_start
                except openai.RateLimitError as exc:
                    self.reservas.concluir(reservation,'http_429_sem_geracao')
                    if envio==3:
                        raise ErroOperacionalLLM('GPU Colab ocupada após três envios') from None
                    try:
                        delay=float(exc.response.headers.get('Retry-After','5'))
                        delay=max(0,min(30,delay)) if math.isfinite(delay) else 5
                    except ValueError:
                        delay=5
                    sleep_start=time.monotonic()
                    until=sleep_start+delay
                    while time.monotonic()<until:
                        if self.parar():
                            raise GeracaoCancelada('Geração cancelada durante espera por GPU')
                        threading.Event().wait(min(.1,max(0,until-time.monotonic())))
                    waited += time.monotonic()-sleep_start
                    continue
                except openai.APIStatusError as exc:
                    self.reservas.concluir(reservation,'http_'+str(exc.status_code))
                    raise ErroOperacionalLLM(f'Colab recusou a geração (HTTP {exc.status_code}): {detalhe_http_seguro(exc.response)}; sem reenvio automático') from None
                except Exception:
                    self.reservas.concluir(reservation,'falha_operacional_consumo_desconhecido')
                    raise ErroOperacionalLLM('Conexão Colab interrompida/timeout ou resposta inválida; consumo desconhecido, sem reenvio') from None
                self.reservas.concluir(reservation,'resposta_recebida')
                break
            try:
                if result.model != self.cfg.modelo or len(result.choices)!=1:
                    raise ValueError()
                choice=result.choices[0]; usage=result.usage
                def tokens(name):
                    value=getattr(usage,name,None) if usage else None
                    if value is not None and (type(value) is not int or value<0):raise ValueError()
                    return value
                estado='completa'
                if choice.message.refusal:estado='recusa'
                elif choice.finish_reason!='stop':estado='truncada_ou_incompleta'
                else:
                    try:Correcao.model_validate_json(choice.message.content)
                    except (ValueError,TypeError):estado='json_invalido'
                r=RespostaColab(choice.message.content, choice.message.refusal, choice.finish_reason,
                    result.model, result.system_fingerprint, self.cfg.seed,
                    tokens('prompt_tokens'),tokens('completion_tokens'),round(time.monotonic()-start,3),
                    key,self.identidade,round(waited,3),round(request_seconds,3),envio,
                    self.ambiente,self.endpoint,estado)
            except Exception:
                raise ErroOperacionalLLM('Resposta Colab incompatível com o protocolo; geração não aplicada') from None
            if estado=='completa':
                atomic_json(path,{'chave':key,'resposta':r.to_dict(),'resposta_sha256':sha(r.to_dict())})
            return r
