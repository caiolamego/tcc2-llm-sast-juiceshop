"""Erros públicos de inferência: metadados seguros, sem corpo HTTP ou credenciais."""
import math
import openai


class ErroOperacionalLLM(RuntimeError):
    def __init__(self, mensagem, *, categoria='operacional', fatal=True, envios=0,
                 historico=None, status_http=None):
        super().__init__(mensagem)
        self.categoria, self.fatal = categoria, fatal
        self.envios, self.historico = envios, historico or []
        self.status_http = status_http

    def metadados(self):
        return {'categoria': self.categoria, 'fatal': self.fatal,
                'chamadas_enviadas': self.envios, 'status_http': self.status_http,
                'historico': self.historico, 'custo_usd': None, 'tokens_entrada': None,
                'tokens_saida': None}


class GeracaoCancelada(ErroOperacionalLLM):
    pass


def classificar(exc):
    """Não serializa mensagens remotas: podem conter URL, token ou prompt."""
    status = getattr(exc, 'status_code', None)
    code = getattr(exc, 'code', None)
    if isinstance(exc, openai.APITimeoutError): return 'timeout', True, False, status
    if isinstance(exc, openai.APIConnectionError): return 'conexao', True, False, status
    if status == 429:
        if code in ('insufficient_quota', 'billing_hard_limit_reached', 'usage_limit_reached'):
            return 'cota_esgotada', False, True, status
        return 'rate_limit', True, False, status
    if status in (408, 409) or status is not None and status >= 500:
        return 'servidor' if status >= 500 else 'http_transitorio', True, False, status
    if status in (401, 403): return 'autenticacao_permissao', False, True, status
    if isinstance(exc, openai.APIStatusError): return 'requisicao_invalida', False, False, status
    return 'resposta_invalida', False, False, status


def atraso(exc, envio):
    """Retry-After numérico respeitado até 60s; backoff finito quando ausente."""
    response = getattr(exc, 'response', None)
    try:
        delay = float(response.headers.get('retry-after', 'nan')) if response is not None else math.nan
        if math.isfinite(delay) and delay >= 0: return min(60., delay)
    except (TypeError, ValueError): pass
    return min(60., 2. ** envio)
