"""Perfis OpenAI usados no experimento; nenhuma leitura de credenciais ou rede."""
import re

MODELOS_OPENAI = ('gpt-4.1-mini', 'gpt-5.6-luna', 'gpt-6-luna')
MAX_TOKENS_SAIDA = 4096
PERFIL_VERSAO = 'openai_sem_raciocinio_v1'


def validar_modelo(modelo):
    if not isinstance(modelo, str) or modelo not in MODELOS_OPENAI:
        raise ValueError('Modelo selecionável inválido; use ' + ', '.join(MODELOS_OPENAI))
    return modelo


def familia_modelo(modelo):
    # Snapshots retornados pela API são vinculados à família exata, nunca por prefixo livre.
    if isinstance(modelo, str):
        for base in MODELOS_OPENAI:
            if modelo == base or re.fullmatch(re.escape(base) + r'-\d{4}-\d{2}-\d{2}', modelo):
                return base
    raise ValueError('Modelo OpenAI sem perfil experimental cadastrado')


def parametros_geracao(modelo, seed=42):
    params = {'temperature': 0, 'max_completion_tokens': MAX_TOKENS_SAIDA}
    if familia_modelo(modelo) == 'gpt-4.1-mini':
        params['seed'] = seed
    else:
        # Nenhum raciocínio ativado; seed é omitida nos Luna, não presumida como aceita.
        params['reasoning_effort'] = 'none'
    return params


def modelo_retornado_compativel(solicitado, retornado):
    try:
        familia = familia_modelo(solicitado)
        return familia_modelo(retornado) == familia and (solicitado == familia or solicitado == retornado)
    except ValueError:
        return False
