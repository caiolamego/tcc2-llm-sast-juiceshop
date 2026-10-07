"""Montagem dos prompts (F5.3). Por enquanto so P1_simples.

P1 = papel + tarefa, codigo (arquivo ou janela), restricoes + formato.
Sem alerta SAST e sem RAG (tabela da F5.3). O desenho final dos prompts
(comparacao 2x2) ainda esta em aberto com a orientadora.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

LIMITE_ARQUIVO_COMPLETO = 250  # linhas (D3)
JANELA = 60                    # linhas para cada lado do finding (D3)

ESTRATEGIAS = {"P1": "P1_simples"}

PAPEL = (
    "Voce e um engenheiro de seguranca de aplicacoes especializado em "
    "TypeScript, Node.js e Express."
)

RESTRICOES = """Restricoes obrigatorias:
- Altere o minimo necessario para corrigir a vulnerabilidade. Nao refatore, nao reformate e nao renomeie nada.
- Nao altere arquivos de teste.
- Cada "trecho_original" deve ser copiado LITERALMENTE do codigo fornecido (mesmos espacos, quebras de linha e pontuacao) e deve aparecer UMA unica vez no arquivo. Inclua linhas vizinhas se precisar para torna-lo unico.
- Preserve o comportamento funcional existente.
- Em "arquivo", use exatamente o caminho relativo informado acima."""

FORMATO = """Formato da resposta: um objeto JSON com os campos
vulnerabilidade_identificada, causa_da_vulnerabilidade, estrategia_de_correcao,
edicoes (lista de {arquivo, trecho_original, trecho_corrigido}),
justificativa_tecnica e limitacoes_da_correcao."""


@dataclass
class PromptMontado:
    estrategia: str            # nome completo, ex. P1_simples
    arquivo: str
    modo_contexto: str         # arquivo_completo | janela_contexto
    linha_ini_contexto: int    # 1-indexado, inclusivo
    linha_fim_contexto: int
    total_linhas_arquivo: int
    mensagens: list[dict]
    hash_prompt: str           # sha256 das mensagens (sem modelo/seed)

    def to_dict(self) -> dict:
        return asdict(self)


def _contexto(linhas: list[str], ini: int, fim: int) -> tuple[str, str, int, int]:
    total = len(linhas)
    if total <= LIMITE_ARQUIVO_COMPLETO:
        return "arquivo_completo", "".join(linhas), 1, total
    a = max(1, ini - JANELA)
    b = min(total, fim + JANELA)
    return "janela_contexto", "".join(linhas[a - 1:b]), a, b


def montar(issue: dict, wt: Path, estrategia: str = "P1") -> PromptMontado:
    if estrategia not in ESTRATEGIAS:
        raise ValueError(f"Estrategia {estrategia} nao implementada (so {list(ESTRATEGIAS)})")

    arquivo = issue["arquivo"]
    # O codigo vem do worktree (commit fixado), nao do campo 'trecho' do
    # catalogo: sem login, o Semgrep devolve 'requires login' nesse campo.
    linhas = (Path(wt) / arquivo).read_text(encoding="utf-8").splitlines(keepends=True)
    modo, codigo, a, b = _contexto(linhas, issue["linha_inicio"], issue["linha_fim"])
    if not codigo.endswith("\n"):
        codigo += "\n"

    if modo == "arquivo_completo":
        cabecalho = f"Arquivo: {arquivo} (completo, {len(linhas)} linhas)"
    else:
        cabecalho = (f"Arquivo: {arquivo} (trecho das linhas {a} a {b} de {len(linhas)}; "
                     "o restante do arquivo nao foi mostrado)")

    usuario = "\n\n".join([
        "Tarefa: identifique e corrija a vulnerabilidade de seguranca presente no codigo abaixo.",
        f"{cabecalho}\n```typescript\n{codigo}```",
        RESTRICOES,
        FORMATO,
    ])
    mensagens = [
        {"role": "system", "content": PAPEL},
        {"role": "user", "content": usuario},
    ]
    h = hashlib.sha256(json.dumps(mensagens, ensure_ascii=False).encode("utf-8")).hexdigest()
    return PromptMontado(ESTRATEGIAS[estrategia], arquivo, modo, a, b, len(linhas), mensagens, h)
