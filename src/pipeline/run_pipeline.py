#!/usr/bin/env python3
"""Orquestracao do experimento (F6, Figura 2 do TCC 1).

Para cada caso do catalogo (em paralelo, ate K worktrees), TODAS as
estrategias rodam, em sequencia, sem parar no aceite (decisao do grupo,
2026-10-13; protocolo, Secao 14). A cadeia do TCC 1 (parar na primeira que
satisfaz R, F e M) e reconstruida em scripts/metricas_execucao.py:

    prompt -> LLM -> patch -> SAST depois -> validacao -> R, F, M -> execucoes.jsonl

Metodo do R (decisao do grupo, 2026-10-07): o "antes" e a varredura do
worktree limpo feita no inicio da sessao (outputs/sast_antes/<EXECUCAO>_baseline_raw.json),
e nao o baseline de referencia, porque os rulesets do registro nao sao
versionados. O baseline de referencia (outputs/sast_antes/baseline_raw.json)
continua sendo a origem do catalogo; as duas varreduras sao comparadas no inicio.

Uso:
    python src/pipeline/run_pipeline.py --execucao E01 --estrategias P1,P2 [--casos JS001,JS003] [--k 4] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import dotenv_values  # noqa: E402
from rich.console import Console  # noqa: E402

from pipeline.caminhos import RAIZ_REPO, rel  # noqa: E402
from pipeline.llm.falso import resposta_falsa  # noqa: E402
from pipeline.llm.openai_client import OrcamentoEsgotado  # noqa: E402
from pipeline.patching.applier import ResultadoAplicacao, aplicar, interpretar  # noqa: E402
from pipeline.prompts import builder  # noqa: E402
from pipeline.registro import ler_execucoes, registrar_execucao  # noqa: E402
from pipeline.sast.filtro import filtrar  # noqa: E402
from pipeline.sast.semgrep_client import (RULESETS, Finding, assinatura, carregar_resultados,  # noqa: E402
                                          executar, ler_exclusoes)
from pipeline.target.workspace import PoolWorktrees  # noqa: E402
from pipeline.validation.runner import ConfigValidacao, validar  # noqa: E402

CATALOGO = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"
# Origem do catalogo vigente (v2, 11 rulesets, 2026-10-13). O de setembro
# (v1, E01/E02) esta em baseline_raw_v1.json.
BASELINE_REFERENCIA = RAIZ_REPO / "outputs" / "sast_antes" / "baseline_raw.json"
# Definicoes de F (protocolo, Secao 13). F e classificacao_final seguem criterio.
DEFS_F = ("sem_separacao", "marcador", "criterio", "criterio_amplo")
PROJETO = "OWASP Juice Shop v20.1.1"

console = Console()


# --------------------------------------------------------------------------
# Saidas
# --------------------------------------------------------------------------

@dataclass
class Saidas:
    """Raiz outputs/ (ou outputs/dry_run/). sast_antes/ e resultados_consolidados/
    sao comuns as execucoes; os artefatos de cada tentativa (prompts,
    respostas_llm, patches, codigos_corrigidos, sast_depois, testes) ficam em
    <raiz>/<EXECUCAO>/, para o .gitignore separar dry-run de resultado real
    com uma linha so (decisao do grupo, 2026-10-13)."""
    raiz: Path
    execucao: str

    def d(self, nome: str) -> Path:
        p = self.raiz / nome
        p.mkdir(parents=True, exist_ok=True)
        return p

    def t(self, nome: str) -> Path:
        return self.d(f"{self.execucao}/{nome}")

    @property
    def execucoes(self) -> Path:
        return self.d("resultados_consolidados") / "execucoes.jsonl"

    def baseline_sessao(self, execucao: str) -> Path:
        return self.d("sast_antes") / f"{execucao}_baseline_raw.json"


def gravar_json(arq: Path, dados) -> Path:
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return arq


# --------------------------------------------------------------------------
# Varredura da sessao
# --------------------------------------------------------------------------

def _elegiveis_dedup(findings: list[Finding]) -> set[str]:
    return {assinatura(f) for f in findings if filtrar(f)[0]}


def varredura_da_sessao(pool: PoolWorktrees, saidas: Saidas, execucao: str,
                        catalogo: list[dict]) -> tuple[list[Finding], dict]:
    """Varre o worktree limpo (ou reaproveita a varredura desta execucao) e
    compara com o baseline de referencia."""
    arq = saidas.baseline_sessao(execucao)
    reutilizada = arq.exists()
    with pool.alugar() as wt:
        if not reutilizada:
            console.log(f"Varredura SAST da sessao em {wt.name} (repositorio inteiro)...")
            inicio = time.monotonic()
            executar(wt, RULESETS, saida_bruta=arq,
                     exclusoes=ler_exclusoes(RAIZ_REPO / "config" / "semgrepignore"))
            console.log(f"  concluida em {time.monotonic() - inicio:.0f}s -> {rel(arq)}")
        sessao = carregar_resultados(arq, wt)
        referencia = carregar_resultados(BASELINE_REFERENCIA, wt)

    versao_sessao = json.loads(arq.read_text(encoding="utf-8")).get("version")
    versao_set = json.loads(BASELINE_REFERENCIA.read_text(encoding="utf-8")).get("version")
    sig_sessao = {assinatura(f) for f in sessao}
    sig_set = {assinatura(f) for f in referencia}
    elig_sessao = _elegiveis_dedup(sessao)
    sig_catalogo = {c["assinatura"] for c in catalogo if c["elegivel"]}
    nome = {assinatura(f): f"{f.check_id} @ {f.path}" for f in sessao + referencia}
    comparacao = {
        "baseline_referencia": rel(BASELINE_REFERENCIA),
        "baseline_sessao": rel(arq),
        "reutilizada": reutilizada,
        "semgrep_versao": {"referencia": versao_set, "sessao": versao_sessao},
        "achados_brutos": {"referencia": len(referencia), "sessao": len(sessao)},
        "assinaturas_brutas_distintas": {"referencia": len(sig_set), "sessao": len(sig_sessao)},
        "so_na_referencia": sorted(nome[s] for s in sig_set - sig_sessao),
        "so_na_sessao": sorted(nome[s] for s in sig_sessao - sig_set),
        "elegiveis_sessao": len(elig_sessao),
        "casos_do_catalogo_ausentes_na_sessao": sorted(
            c["caso_id"] for c in catalogo if c["elegivel"] and c["assinatura"] not in sig_sessao),
        "elegiveis_novos_na_sessao_fora_do_catalogo": sorted(nome[s] for s in elig_sessao - sig_catalogo),
    }
    comparacao["diverge"] = bool(
        comparacao["so_na_referencia"] or comparacao["so_na_sessao"]
        or len(referencia) != len(sessao) or versao_set != versao_sessao)
    gravar_json(saidas.d("sast_antes") / f"{execucao}_comparacao_baseline.json", comparacao)
    return sessao, comparacao


# --------------------------------------------------------------------------
# Uma tentativa
# --------------------------------------------------------------------------

def faixa_regra(issue: dict) -> str | None:
    modo = issue.get("modo_regra")
    if modo == "search":
        return "1_search"
    if modo == "taint":
        return "2_taint_com_saneadores" if issue.get("saneadores_regra") else "3_taint_sem_saneadores"
    return None


def _finding_dict(f: Finding) -> dict:
    d = f.to_dict()
    d["assinatura"] = assinatura(f)
    d["elegivel_protocolo"] = filtrar(f)[0]
    return d


class Contexto:
    """Estado compartilhado entre os workers."""

    def __init__(self, args, saidas: Saidas, sessao: list[Finding], versao_semgrep: str | None):
        self.args = args
        self.saidas = saidas
        self.sessao = sessao
        self.versao_semgrep = versao_semgrep
        self.lock_t4 = threading.Lock()
        self.parar = threading.Event()
        self.lock_custo = threading.Lock()
        self.custo_sessao = 0.0
        self.erros: list[dict] = []
        self.cliente = None
        if not args.dry_run:
            from pipeline.llm.openai_client import ClienteLLM, ConfigLLM
            self.cliente = ClienteLLM(ConfigLLM.do_env())

    def somar_custo(self, usd: float) -> float:
        with self.lock_custo:
            self.custo_sessao += usd
            return self.custo_sessao


def tentativa(ctx: Contexto, issue: dict, estrategia: str, wt: Path, tid: str) -> dict:
    s = ctx.saidas
    args = ctx.args
    PoolWorktrees.restaurar(wt)

    prompt = builder.montar(issue, wt, estrategia)
    gravar_json(s.t("prompts") / f"{tid}.json", prompt.to_dict())

    if args.dry_run:
        texto = resposta_falsa(issue, wt)
        llm = {"modelo": "dry-run", "seed": None, "system_fingerprint": None, "tokens_entrada": 0,
               "tokens_saida": 0, "latencia_s": 0.0, "custo_usd": 0.0, "do_cache": False,
               "finish_reason": None, "recusa": None, "hash_prompt": prompt.hash_prompt}
    else:
        r = ctx.cliente.gerar(prompt.mensagens)
        texto = r.conteudo
        llm = {k: v for k, v in r.to_dict().items() if k != "conteudo"}
    gravar_json(s.t("respostas_llm") / f"{tid}.json", {"texto": texto, **llm})

    correcao = interpretar(texto)
    aplic = correcao if isinstance(correcao, ResultadoAplicacao) else aplicar(wt, correcao)

    linha = {
        "tentativa_id": tid, "execucao": args.execucao, "dry_run": args.dry_run,
        "caso_id": issue["caso_id"], "assinatura": issue["assinatura"], "projeto": PROJETO,
        "arquivo": issue["arquivo"], "linha": issue["linha_inicio"], "check_id": issue["check_id"],
        "cwe": issue["cwe"], "owasp_2025": issue["owasp_2025"], "sigla_vuln": issue["sigla_vuln"],
        "modo_regra": issue.get("modo_regra"), "faixa_regra": faixa_regra(issue),
        "estrategia_prompt": prompt.estrategia,
        "triagem_manual": issue.get("triagem_manual", "nao_triado"),
        # desenho = estrategia do TCC 1 (P1-P4); diagnostico = P1L (protocolo, Secao 12)
        "condicao": "diagnostico" if estrategia in builder.DIAGNOSTICOS else "desenho",
        "usa_rag": prompt.usa_rag,
        "arquivo_rag_recuperado": prompt.arquivo_rag_recuperado,
        "roteiro_status": prompt.roteiro_status, "roteiro_sha256": prompt.roteiro_sha256,
        "modelo": llm["modelo"], "seed": llm["seed"], "system_fingerprint": llm["system_fingerprint"],
        "hash_prompt": prompt.hash_prompt, "do_cache": llm["do_cache"],
        "finish_reason": llm["finish_reason"], "recusa": llm["recusa"],
        "modo_contexto": prompt.modo_contexto,
        "status_aplicacao": aplic.status, "detalhe_aplicacao": aplic.detalhe,
        "arquivos_alterados": aplic.arquivos,
        "R": None, "F": None, "M": None, "tier_falha": None,
        **{f"F_{k}": None for k in DEFS_F},
        **{f"tier_falha_{k}": None for k in DEFS_F},
        **{f"testes_falhos_{df}_{k}": [] for k in DEFS_F[1:] for df in ("d", "f")},
        "novas_issues_qtd": None, "novas_issues_ids": [],
        "testes_falhos_novos": [], "testes_falhos_intermitentes": [], "reexecucoes": 0,
        "tokens_entrada": llm["tokens_entrada"], "tokens_saida": llm["tokens_saida"],
        "duracao_llm_s": llm["latencia_s"], "duracao_sast_s": None, "duracao_validacao_s": None,
        "custo_usd": llm["custo_usd"], "classificacao_final": None,
        "versao_semgrep": ctx.versao_semgrep, "worktree": wt.name,
        "sast_depois": None, "sast_depois_raw": None,
        "artefatos": {"prompt": rel(s.t("prompts") / f"{tid}.json"),
                      "resposta": rel(s.t("respostas_llm") / f"{tid}.json")},
    }

    if aplic.status != "aplicado":
        linha["classificacao_final"] = f"nao_aplicada:{aplic.status}"
        for k in DEFS_F:
            linha[f"classificacao_{k}"] = linha["classificacao_final"]
        return linha

    diff = subprocess.run(["git", "diff"], cwd=wt, capture_output=True, text=True, timeout=60).stdout
    arq_diff = s.t("patches") / f"{tid}.diff"
    arq_diff.write_text(diff, encoding="utf-8")
    for a in aplic.arquivos:
        destino = s.t("codigos_corrigidos") / tid / a
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wt / a, destino)
    linha["artefatos"]["patch"] = rel(arq_diff)

    # SAST depois: so os arquivos tocados (a analise do Semgrep e por arquivo).
    alvos = sorted(set(aplic.arquivos) | {issue["arquivo"]})
    arq_raw = s.t("sast_depois") / f"{tid}_raw.json"
    inicio = time.monotonic()
    depois = executar(wt, RULESETS, saida_bruta=arq_raw, caminhos=alvos)
    linha["duracao_sast_s"] = round(time.monotonic() - inicio, 2)
    antes = [f for f in ctx.sessao if f.path in alvos]

    sig_alvo = issue["assinatura"]
    sig_depois = {assinatura(f) for f in depois}
    novas = sorted(_elegiveis_dedup(depois) - _elegiveis_dedup(antes))
    linha["R"] = int(sig_alvo not in sig_depois)
    linha["M"] = int(not novas)
    linha["novas_issues_qtd"] = len(novas)
    linha["novas_issues_ids"] = novas
    linha["ocorrencias_alvo"] = {"antes": sum(assinatura(f) == sig_alvo for f in antes),
                                 "depois": sum(assinatura(f) == sig_alvo for f in depois)}
    linha["sast_depois"] = [_finding_dict(f) for f in depois]
    linha["sast_depois_raw"] = rel(arq_raw)

    cfg = ConfigValidacao(lock_t4=ctx.lock_t4)
    v = validar(wt, aplic.arquivos, cfg)
    gravar_json(s.t("testes") / f"{tid}.json", v.to_dict())
    linha["artefatos"]["validacao"] = rel(s.t("testes") / f"{tid}.json")
    # F e tier_falha seguem d_criterio (Secao 7.1); as quatro versoes vao juntas
    # para a analise de sensibilidade (Secao 13).
    linha["F"] = int(v.passou)
    linha["tier_falha"] = v.tier_falha
    for k in DEFS_F:
        linha[f"F_{k}"] = int(getattr(v, f"F_{k}"))
        linha[f"tier_falha_{k}"] = getattr(v, f"tier_falha_{k}")
    for k in DEFS_F[1:]:
        for df in ("d", "f"):
            linha[f"testes_falhos_{df}_{k}"] = getattr(v, f"testes_falhos_{df}_{k}")
    linha["testes_falhos_novos"] = v.testes_falhos_novos
    linha["testes_falhos_intermitentes"] = v.testes_falhos_intermitentes
    linha["reexecucoes"] = v.reexecucoes
    linha["duracao_validacao_s"] = v.duracao_s

    for k in DEFS_F:
        f = linha[f"F_{k}"]
        linha[f"classificacao_{k}"] = ("aceita" if linha["R"] and f and linha["M"] else
                                       f"rejeitada:R{linha['R']}F{f}M{linha['M']}")
    linha["classificacao_final"] = linha["classificacao_criterio"]
    return linha


# --------------------------------------------------------------------------
# Um caso (estrategias em sequencia)
# --------------------------------------------------------------------------

def nome_tentativa(issue: dict, estrategia: str, execucao: str) -> str:
    return "_".join([issue["caso_id"], issue["owasp_2025"], issue["sigla_vuln"], estrategia, execucao])


def processar_caso(ctx: Contexto, pool: PoolWorktrees, issue: dict,
                   feitas: dict[str, dict]) -> None:
    """Todas as estrategias do desenho e as condicoes de diagnostico, sem
    parar no aceite (protocolo, Secao 14): a leitura por estrategia so e
    valida se cada uma rodou em todos os casos. A cadeia do TCC 1 e
    reconstruida nas metricas. Na retomada, so roda o que falta."""
    caso = issue["caso_id"]
    pendentes = [(e, tid) for e in ctx.args.estrategias + ctx.args.diagnosticos
                 if (tid := nome_tentativa(issue, e, ctx.args.execucao)) not in feitas]
    if not pendentes:
        console.log(f"[dim]{caso}: nada pendente (retomada)[/]")
        return

    with pool.alugar() as wt:
        for e, tid in pendentes:
            if ctx.parar.is_set():
                return
            try:
                linha = tentativa(ctx, issue, e, wt, tid)
            except OrcamentoEsgotado as ex:
                ctx.parar.set()
                console.log(f"[bold red]Orcamento esgotado: {ex}. Parando a sessao.[/]")
                return
            except Exception as ex:  # interrompe so este caso; a retomada refaz
                ctx.erros.append({"tentativa_id": tid, "erro": f"{type(ex).__name__}: {ex}"})
                console.log(f"[red]{tid}: ERRO {type(ex).__name__}: {ex}. Caso interrompido.[/]")
                return
            registrar_execucao(linha, wt, ctx.saidas.execucoes)
            # Resposta do cache nao e cobrada de novo (o custo na linha e o da chamada original).
            total = ctx.somar_custo(0.0 if linha["do_cache"] else (linha["custo_usd"] or 0.0))
            cor = "green" if linha["classificacao_final"] == "aceita" else "yellow"
            fs = "/".join(str(linha.get(f"F_{k}")) for k in DEFS_F)
            console.log(f"[{cor}]{tid}[/] {linha['classificacao_final']} "
                        f"(F sem/marc/crit/amplo={fs}) "
                        f"(aplic={linha['status_aplicacao']}, tier_falha={linha['tier_falha']}, "
                        f"novas={linha['novas_issues_qtd']}) | US$ sessao {total:.5f}")


# --------------------------------------------------------------------------
# Sessao
# --------------------------------------------------------------------------

def registrar_sessao(saidas: Saidas, execucao: str, info: dict) -> Path:
    """Acrescenta a sessao ao historico da execucao (tambem quando aborta)."""
    arq = saidas.d("resultados_consolidados") / f"{execucao}_sessoes.json"
    historico = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    return gravar_json(arq, historico + [info])


def checar_ambiente(pool: PoolWorktrees, k: int, lock_t4: threading.Lock) -> list[dict]:
    """Cenario 1 da F4.3 em cada worktree: sem alteracao, a validacao passa."""
    def um(_):
        with pool.alugar() as wt:
            v = validar(wt, [], ConfigValidacao(lock_t4=lock_t4))
            # Sem alteracao nenhum teste novo pode falhar, nem de D.
            return {"worktree": wt.name, "passou": v.F_sem_separacao,
                    "tier_falha": v.tier_falha_sem_separacao,
                    "motivos": {t.tier: t.motivo for t in v.tiers},
                    "testes_falhos_novos": v.testes_falhos_novos,
                    "testes_falhos_intermitentes": v.testes_falhos_intermitentes,
                    "duracao_s": v.duracao_s}
    with ThreadPoolExecutor(max_workers=k) as ex:
        return list(ex.map(um, range(k)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execucao", required=True, help="ex.: E01 (oficial) ou DRY01")
    ap.add_argument("--estrategias", default="P1,P2,P3,P4")
    ap.add_argument("--diagnosticos", default="",
                    help="condicoes de diagnostico fora da cadeia, ex.: P1L (protocolo, Secao 12)")
    ap.add_argument("--casos", default=None, help="ex.: JS001,JS003 (padrao: todo o catalogo)")
    ap.add_argument("--k", type=int, default=4, help="worktrees em paralelo")
    ap.add_argument("--dry-run", action="store_true", help="resposta falsa, sem chamar a API")
    ap.add_argument("--pular-checagem-ambiente", action="store_true")
    args = ap.parse_args()
    args.estrategias = [e.strip() for e in args.estrategias.split(",") if e.strip()]
    args.diagnosticos = [e.strip() for e in args.diagnosticos.split(",") if e.strip()]
    if not re.fullmatch(r"[A-Z]+[0-9]+", args.execucao):
        raise SystemExit("ERRO: --execucao no formato E01, DRY01 (vira pasta em outputs/)")
    if set(args.estrategias) & set(builder.DIAGNOSTICOS):
        raise SystemExit("ERRO: P1L e condicao de diagnostico; use --diagnosticos P1L")
    if set(args.diagnosticos) - set(builder.DIAGNOSTICOS):
        raise SystemExit(f"ERRO: diagnosticos validos: {list(builder.DIAGNOSTICOS)}")

    # Estrategias: falha cedo e com mensagem clara.
    try:
        for e in args.estrategias + args.diagnosticos:
            builder.verificar_disponivel(e)
    except builder.EstrategiaIndisponivel as ex:
        raise SystemExit(f"ERRO: {ex}")
    if not args.dry_run and set(args.estrategias) & builder.COM_ROTEIRO:
        _, status, _ = builder.carregar_roteiro()
        if status != builder.STATUS_APROVADO:
            raise SystemExit(f"ERRO: roteiro do P2/P4 com STATUS {status} "
                             f"({rel(builder.ARQ_ROTEIRO)}). Chamada real so com STATUS: APROVADO.")

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    casos = [c for c in catalogo if c["elegivel"]]
    if args.casos:
        pedidos = [c.strip() for c in args.casos.split(",")]
        desconhecidos = set(pedidos) - {c["caso_id"] for c in casos}
        if desconhecidos:
            raise SystemExit(f"ERRO: casos fora do catalogo elegivel: {sorted(desconhecidos)}")
        casos = [c for c in casos if c["caso_id"] in pedidos]

    saidas = Saidas(RAIZ_REPO / "outputs" / ("dry_run" if args.dry_run else ""), args.execucao)
    env = dotenv_values(RAIZ_REPO / ".env")
    pool = PoolWorktrees(RAIZ_REPO / "workspace", k=args.k, commit_esperado=env.get("JUICESHOP_COMMIT"))
    sessao_info = {
        "execucao": args.execucao, "dry_run": args.dry_run, "estrategias": args.estrategias,
        "diagnosticos": args.diagnosticos,
        "casos": [c["caso_id"] for c in casos], "k": args.k,
        "inicio": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_alvo": env.get("JUICESHOP_COMMIT"),
    }
    console.rule(f"Execucao {args.execucao}{' (dry-run)' if args.dry_run else ''}: "
                 f"{len(casos)} casos x {args.estrategias} + diagnosticos {args.diagnosticos}, K={args.k}")

    lock_t4 = threading.Lock()
    if not args.pular_checagem_ambiente:
        console.log("Checagem de ambiente: validacao sem alteracao em cada worktree...")
        amb = checar_ambiente(pool, args.k, lock_t4)
        sessao_info["checagem_ambiente"] = amb
        for a in amb:
            console.log(f"  {a['worktree']}: {'OK' if a['passou'] else 'FALHOU'} ({a['duracao_s']}s)"
                        + (f" intermitentes={a['testes_falhos_intermitentes']}" if a["testes_falhos_intermitentes"] else ""))
        if not all(a["passou"] for a in amb):
            sessao_info["abortada"] = "checagem_ambiente"
            registrar_sessao(saidas, args.execucao, sessao_info)
            raise SystemExit("ERRO: worktree sem alteracao reprovado na validacao. "
                             "Problema de ambiente, nao do pipeline (F4.3).")

    sessao, comp = varredura_da_sessao(pool, saidas, args.execucao, catalogo)
    sessao_info["comparacao_baseline"] = rel(saidas.d("sast_antes") / f"{args.execucao}_comparacao_baseline.json")
    console.log(f"Baseline referencia x sessao: {comp['achados_brutos']['referencia']} x "
                f"{comp['achados_brutos']['sessao']} achados brutos, "
                f"semgrep {comp['semgrep_versao']['referencia']} x {comp['semgrep_versao']['sessao']}")
    if comp["diverge"]:
        console.log(f"[bold yellow]AVISO: varreduras divergem. So na referencia: {comp['so_na_referencia']}; "
                    f"so na sessao: {comp['so_na_sessao']}[/]")
    ausentes = set(comp["casos_do_catalogo_ausentes_na_sessao"])
    if ausentes & {c["caso_id"] for c in casos}:
        console.log(f"[bold yellow]Casos sem o alerta na varredura da sessao (R nao mensuravel, pulados): "
                    f"{sorted(ausentes)}[/]")
    sessao_info["casos_pulados_alerta_ausente"] = sorted(ausentes & {c["caso_id"] for c in casos})
    casos = [c for c in casos if c["caso_id"] not in ausentes]

    feitas = {l["tentativa_id"]: l for l in ler_execucoes(saidas.execucoes)
              if l.get("execucao") == args.execucao}
    if feitas:
        console.log(f"Retomada: {len(feitas)} tentativa(s) ja registradas para {args.execucao}")

    versao = comp["semgrep_versao"]["sessao"]
    ctx = Contexto(args, saidas, sessao, versao)
    ctx.lock_t4 = lock_t4
    inicio = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.k) as ex:
        list(ex.map(lambda c: processar_caso(ctx, pool, c, feitas), casos))

    sessao_info.update({
        "fim": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "custo_usd_sessao": round(ctx.custo_sessao, 6),
        "erros": ctx.erros, "interrompida_por_orcamento": ctx.parar.is_set(),
    })
    arq_sessoes = registrar_sessao(saidas, args.execucao, sessao_info)

    linhas = [l for l in ler_execucoes(saidas.execucoes) if l.get("execucao") == args.execucao]
    aceitas = {l["caso_id"] for l in linhas if l["classificacao_final"] == "aceita"
               and l.get("condicao", "desenho") == "desenho"}
    console.rule("Resumo")
    console.log(f"{len(linhas)} tentativas registradas, {len(aceitas)} caso(s) com correcao aceita, "
                f"{len(ctx.erros)} erro(s), US$ {ctx.custo_sessao:.5f} nesta sessao")
    console.log(f"Registro: {rel(saidas.execucoes)} | sessao: {rel(arq_sessoes)}")
    if ctx.erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
