"""Montagem dos prompts (F5.3). Implementados: P1_simples e P2_raciocinio_guiado.

P1 = papel + tarefa, codigo (arquivo ou janela), restricoes + formato.
P2 = P1 + roteiro de raciocinio em etapas (config/prompts/).
Sem alerta SAST e sem RAG em P1/P2 (tabela da F5.3; fatorial 2x2 removido,
cronograma-acelerado.md). P3/P4 dependem de knowledge_base/ (F5.4).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

LIMITE_ARQUIVO_COMPLETO = 250  # linhas (D3)
JANELA = 60                    # linhas para cada lado do finding (D3)

ESTRATEGIAS = {
    "P1": "P1_simples",
    "P2": "P2_raciocinio_guiado",
    "P3": "P3_rag",
    "P4": "P4_rag_raciocinio_guiado",
}
COM_ROTEIRO = {"P2", "P4"}
COM_RAG = {"P3", "P4"}
# Condicao de diagnostico (protocolo, Secao 12): NAO e estrategia do desenho
# do TCC 1. P1L = P1 + bloco com a localizacao e a identificacao do alerta.
DIAGNOSTICOS = {"P1L": "P1L_diagnostico_localizacao"}
COM_ALERTA = {"P1L"}

RAIZ_REPO = Path(__file__).resolve().parents[3]
ARQ_ROTEIRO = RAIZ_REPO / "config" / "prompts" / "roteiro_raciocinio_guiado.md"
DIR_KB = RAIZ_REPO / "knowledge_base"
STATUS_APROVADO = "APROVADO"


class EstrategiaIndisponivel(RuntimeError):
    pass

PAPEL = (
    "Voce e um engenheiro de seguranca de aplicacoes especializado em "
    "TypeScript, Node.js e Express."
)

# Comuns a P1-P4 e CONGELADAS desde 2026-10-07 (protocolo, Secao 10): nenhuma
# alteracao com base em resultados da execucao completa.
RESTRICOES = """Restricoes obrigatorias:
- Altere o minimo necessario para corrigir a vulnerabilidade. Nao refatore, nao reformate e nao renomeie nada.
- Não altere mensagens de erro, textos visíveis ao usuário, nomes de identificadores nem assinaturas de funções existentes.
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
    usa_rag: bool = False
    arquivo_rag_recuperado: str | None = None
    roteiro_status: str | None = None   # APROVADO | RASCUNHO (so P2/P4)
    roteiro_sha256: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _contexto(linhas: list[str], ini: int, fim: int) -> tuple[str, str, int, int]:
    total = len(linhas)
    if total <= LIMITE_ARQUIVO_COMPLETO:
        return "arquivo_completo", "".join(linhas), 1, total
    a = max(1, ini - JANELA)
    b = min(total, fim + JANELA)
    return "janela_contexto", "".join(linhas[a - 1:b]), a, b


SECAO_BLOCO = "## Bloco a ser inserido no prompt"


def carregar_roteiro() -> tuple[str, str, str]:
    """(texto, status, sha256) do roteiro do P2/P4.

    O arquivo e um documento (fonte no TCC 1, correspondencia com os campos,
    congelamento). So vai para o prompt o primeiro bloco cercado por ``` da
    secao SECAO_BLOCO; a primeira linha do arquivo e 'STATUS: <x>'.
    """
    if not ARQ_ROTEIRO.exists():
        raise EstrategiaIndisponivel(f"Roteiro do P2/P4 ausente: {ARQ_ROTEIRO.relative_to(RAIZ_REPO)}")
    conteudo = ARQ_ROTEIRO.read_text(encoding="utf-8")
    status = conteudo.partition("\n")[0].removeprefix("STATUS:").strip()
    _, achou, depois = conteudo.partition(SECAO_BLOCO)
    partes = depois.split("```")
    if not achou or len(partes) < 3:
        raise EstrategiaIndisponivel(
            f"{ARQ_ROTEIRO.relative_to(RAIZ_REPO)}: bloco cercado por ``` nao encontrado "
            f"na secao '{SECAO_BLOCO}'")
    texto = partes[1].strip("\n")
    return texto, status, hashlib.sha256(texto.encode("utf-8")).hexdigest()


def verificar_disponivel(estrategia: str) -> None:
    """Falha cedo, com mensagem clara, para estrategia sem insumo pronto."""
    if estrategia not in ESTRATEGIAS and estrategia not in DIAGNOSTICOS:
        raise EstrategiaIndisponivel(f"Estrategia desconhecida: {estrategia} "
                                     f"(validas: {list(ESTRATEGIAS) + list(DIAGNOSTICOS)})")
    if estrategia in COM_RAG and not (DIR_KB / "_index.yaml").exists():
        raise EstrategiaIndisponivel(
            f"{estrategia} ({ESTRATEGIAS[estrategia]}) depende de knowledge_base/_index.yaml "
            "(F5.4), que ainda nao existe. Rode com --estrategias P1,P2 ate a base ficar pronta.")
    if estrategia in COM_ROTEIRO:
        carregar_roteiro()


def bloco_alerta(issue: dict) -> str:
    """Localizacao e identificacao do alerta (P1L): arquivo, linha, regra, CWE, mensagem."""
    linha = (str(issue["linha_inicio"]) if issue["linha_inicio"] == issue["linha_fim"]
             else f"{issue['linha_inicio']} a {issue['linha_fim']}")
    return "\n".join([
        "Alerta da ferramenta de analise estatica (Semgrep) que deve ser corrigido:",
        f"- Arquivo: {issue['arquivo']}",
        f"- Linha: {linha}",
        f"- Regra: {issue['check_id']}",
        f"- CWE: {', '.join(issue['cwe'])}",
        f"- Mensagem: {issue['mensagem']}",
    ])


def montar(issue: dict, wt: Path, estrategia: str = "P1") -> PromptMontado:
    verificar_disponivel(estrategia)
    if estrategia in COM_RAG:
        raise EstrategiaIndisponivel(f"{estrategia}: montagem com RAG ainda nao implementada (F5.4)")

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

    blocos = [
        "Tarefa: identifique e corrija a vulnerabilidade de seguranca presente no codigo abaixo.",
        f"{cabecalho}\n```typescript\n{codigo}```",
    ]
    roteiro_status = roteiro_sha = None
    if estrategia in COM_ALERTA:
        blocos.append(bloco_alerta(issue))
    if estrategia in COM_ROTEIRO:
        roteiro, roteiro_status, roteiro_sha = carregar_roteiro()
        blocos.append(roteiro)
    usuario = "\n\n".join(blocos + [RESTRICOES, FORMATO])
    mensagens = [
        {"role": "system", "content": PAPEL},
        {"role": "user", "content": usuario},
    ]
    h = hashlib.sha256(json.dumps(mensagens, ensure_ascii=False).encode("utf-8")).hexdigest()
    nome = ESTRATEGIAS.get(estrategia) or DIAGNOSTICOS[estrategia]
    return PromptMontado(nome, arquivo, modo, a, b, len(linhas), mensagens, h,
                         roteiro_status=roteiro_status, roteiro_sha256=roteiro_sha)
