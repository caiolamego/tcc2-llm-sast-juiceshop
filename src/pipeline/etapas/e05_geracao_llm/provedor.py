"""Configuração/fábrica comum; leitura offline não cria cliente nem consulta rede."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e05_geracao_llm.protocolo_colab import read_json, sha, validar_manifesto
from pipeline.etapas.e05_geracao_llm.esquema import response_format


from pipeline.etapas.e05_geracao_llm.erros import ErroOperacionalLLM, GeracaoCancelada


def politica_cache(valores):
    modo = valores.get("LLM_CACHE") or "desligado"
    if modo not in ("desligado", "leitura-escrita"):
        raise ValueError("LLM_CACHE deve ser desligado ou leitura-escrita")
    return modo


def valores_env(arquivo=None):
    return {**dotenv_values(arquivo or RAIZ_REPO / '.env'),
            **{k:v for k,v in os.environ.items() if k.startswith(('OPENAI_', 'COLAB_', 'LLM_', 'MAX_'))}}


def provedor(arquivo=None):
    value = valores_env(arquivo).get('LLM_PROVIDER') or 'openai'
    if value not in ('openai', 'colab'):
        raise ValueError('LLM_PROVIDER deve ser openai ou colab')
    return value


@dataclass(frozen=True)
class ConfigColab:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    modelo: str
    manifesto: dict
    seed: int = 42
    timeout: float = 600
    max_tokens: int = 4096
    max_chamadas: int = 400
    max_in_flight: int = 1
    manifesto_path: Path | None = field(default=None, repr=False)
    cache_llm: str = "desligado"

    @classmethod
    def do_env(cls, arquivo=None):
        v = valores_env(arquivo)
        def required(key):
            value = v.get(key) or ''
            if not value.strip() or '<' in value or '>' in value:
                raise ValueError(f'{key} ausente ou placeholder')
            return value.strip()
        url = required('COLAB_BASE_URL').rstrip('/')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path.endswith('/v1'):
            raise ValueError('COLAB_BASE_URL requer HTTPS, caminho /v1 e nenhuma credencial na URL')
        key = required('COLAB_API_KEY')
        if any(ch.isspace() for ch in key):
            raise ValueError('COLAB_API_KEY inválido')
        model = required('COLAB_MODEL')
        path = Path(required('COLAB_MODEL_MANIFEST'))
        path = path if path.is_absolute() else RAIZ_REPO / path
        manifest = validar_manifesto(read_json(path))
        cfg = cls(url, key, model, manifest,
                  int(v.get('COLAB_SEED') or 42), float(v.get('COLAB_TIMEOUT_S') or 600),
                  int(v.get('COLAB_MAX_OUTPUT_TOKENS') or 4096), int(v.get('MAX_LLM_CALLS') or 400),
                  int(v.get('COLAB_MAX_IN_FLIGHT') or 1), manifesto_path=path.resolve(), cache_llm=politica_cache(v))
        if model != manifest['cientifica']['modelo']:
            raise ValueError('COLAB_MODEL diverge do manifesto')
        if not math.isfinite(cfg.timeout) or cfg.timeout <= 0 or cfg.max_tokens <= 0 or cfg.max_tokens > manifest['cientifica']['saida_maxima_tokens'] or cfg.max_chamadas <= 0 or cfg.max_in_flight != 1:
            raise ValueError('Limites Colab inválidos; COLAB_MAX_IN_FLIGHT deve ser 1')
        return cfg

    def identidade(self):
        manifest = validar_manifesto(read_json(self.manifesto_path) if self.manifesto_path else self.manifesto)
        impl = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))
                if p.name in ('provedor.py', 'cliente_colab.py', 'protocolo_colab.py', 'esquema.py', 'erros.py')}
        return {'provedor': 'colab', 'modelo': self.modelo, 'cache_llm': self.cache_llm,
                'modelo_identidade_sha256': manifest['identidade_sha256'],
                'cientifica': manifest['cientifica'],
                'geracao': {'seed': self.seed, 'temperature': 0, 'max_completion_tokens': self.max_tokens,
                            'schema_sha256': sha(response_format())},
                'transporte': {'timeout_s': self.timeout, 'max_in_flight': 1, 'repeticao': 'somente_429_3_envios_v1'},
                'implementacao': impl}


def identidade_offline(arquivo=None, simulada=False, modelo=None):
    if modelo is not None:
        from pipeline.etapas.e05_geracao_llm.modelos import validar_modelo
        validar_modelo(modelo)
    if simulada:
        return {'provedor': 'simulado', 'modelo': 'dry-run',
                **({'modelo_solicitado': modelo} if modelo else {})}
    if modelo is None and provedor(arquivo) == 'colab':
        return ConfigColab.do_env(arquivo).identidade()
    from pipeline.etapas.e05_geracao_llm.cliente_openai import MAX_TENTATIVAS, TIMEOUT_REQUISICAO_S, _precos, ARQ_PRECOS
    from pipeline.etapas.e05_geracao_llm.modelos import parametros_geracao, PERFIL_VERSAO
    import openai
    v = valores_env(arquivo)
    escolhido = modelo or v.get('OPENAI_MODEL') or 'gpt-4.1-mini'
    params = parametros_geracao(escolhido, int(v.get('OPENAI_SEED') or 42))
    return {'provedor': 'openai', 'modelo': escolhido, 'cache_llm': politica_cache(v),
            'perfil_versao': PERFIL_VERSAO,
            'geracao': {**params, 'schema_sha256': sha(response_format())},
            'precos': _precos(escolhido),
            'precos_sha256': hashlib.sha256(ARQ_PRECOS.read_bytes()).hexdigest(),
            'sdk_openai': openai.__version__,
            'transporte': {'timeout_s': TIMEOUT_REQUISICAO_S, 'tentativas': MAX_TENTATIVAS, 'politica': 'transitorios_limitados_v2'},
            'implementacao': {name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                             for name in ('modelos.py', 'provedor.py', 'cliente_openai.py', 'erros.py', 'esquema.py')}}


def criar_cliente(arquivo=None, parar=None, modelo=None):
    if modelo is None and provedor(arquivo) == 'colab':
        from pipeline.etapas.e05_geracao_llm.cliente_colab import ClienteColab
        return ClienteColab(ConfigColab.do_env(arquivo), parar=parar)
    from pipeline.etapas.e05_geracao_llm.cliente_openai import ClienteLLM, ConfigLLM
    return ClienteLLM(ConfigLLM.do_env(arquivo or RAIZ_REPO / '.env', modelo=modelo), parar=parar)


def resumo_publico(arquivo=None, modelo=None):
    try:
        identity = identidade_offline(arquivo, modelo=modelo)
        return {'provedor': identity['provedor'], 'modelo': identity['modelo'],
                'revisao': identity.get('cientifica', {}).get('revisao', '')[:12],
                'estado': 'configurado_offline' if identity['provedor']=='colab' else 'configurado',
                'conexao': 'não verificada' if identity['provedor']=='colab' else 'não consultada'}
    except (ValueError, OSError, TypeError):
        return {'provedor': 'indisponivel', 'modelo': None, 'estado': 'configuracao_invalida', 'conexao': 'não verificada'}


def texto_aplicavel(resposta):
    """Preserva texto bruto no artefato; resposta incompleta nunca vira edição."""
    if resposta.finish_reason != 'stop' or getattr(resposta, 'recusa', None):
        return None
    return resposta.conteudo


def ambiente_alvo(extra=None):
    # Nunca repassar credenciais de inferência herdadas do shell ao alvo/SAST.
    blocked=('OPENAI_', 'COLAB_', 'NGROK_')
    return {k:v for k,v in {**os.environ, **(extra or {})}.items() if not k.startswith(blocked)}
