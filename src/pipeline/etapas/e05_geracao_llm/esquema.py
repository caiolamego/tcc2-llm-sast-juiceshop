"""Formato estruturado da resposta da LLM (F5.1, D3).

Os seis campos de Correcao sao os da Secao 3.6 do TCC 1, com
'codigo_corrigido' trocado por 'edicoes' (D3).
extra="forbid" faz o Pydantic gerar additionalProperties: false, e campos
sem valor padrao vao todos para 'required' -- as duas exigencias do modo
strict da API.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Edicao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arquivo: str = Field(description="Caminho relativo do arquivo a ser alterado")
    trecho_original: str = Field(description="Trecho EXATO existente no arquivo, unico")
    trecho_corrigido: str = Field(description="Trecho que substituira o original")


class Correcao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vulnerabilidade_identificada: str
    causa_da_vulnerabilidade: str
    estrategia_de_correcao: str
    edicoes: list[Edicao]
    justificativa_tecnica: str
    limitacoes_da_correcao: str


NOME_SCHEMA = "correcao"


def schema_strict() -> dict:
    """JSON Schema de Correcao para response_format (strict: true)."""
    return Correcao.model_json_schema()


def response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {"name": NOME_SCHEMA, "strict": True, "schema": schema_strict()},
    }
