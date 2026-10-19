#!/usr/bin/env python3
"""Orquestracao do experimento (F6, Figura 2 do TCC 1).

Para cada caso do catalogo (em paralelo, ate K worktrees), as estrategias
rodam em sequencia e param na primeira que satisfaz R, F e M:

    prompt -> LLM -> patch -> SAST depois -> validacao -> R, F, M -> execucoes.jsonl

Metodo do R (decisao do grupo, 2026-10-07): o "antes" e a varredura do
worktree limpo feita no inicio da sessao (outputs/sast_antes/<EXECUCAO>_baseline_raw.json),
e nao o baseline de setembro, porque os rulesets do registro nao sao
versionados. O baseline de setembro continua sendo a origem do catalogo; as
duas varreduras sao comparadas no inicio.

Uso:
    python src/pipeline/run_pipeline.py --execucao E01 --estrategias P1,P2 [--casos JS001,JS003] [--k 4] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
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
from pipeline.llm.falso import resposta_falsa, resposta_falsa_ampliada  # noqa: E402
from pipeline.llm.openai_client import OrcamentoEsgotado  # noqa: E402
from pipeline.patching.applier import VERSAO as VERSAO_APLICADOR, ResultadoAplicacao, aplicar, interpretar  # noqa: E402
from pipeline.prompts import builder  # noqa: E402
from pipeline.registro import ler_execucoes, registrar_execucao  # noqa: E402
from pipeline.sast.filtro import filtrar  # noqa: E402
from pipeline.sast.semgrep_client import (RULESETS, Finding, assinatura, carregar_resultados,  # noqa: E402
                                          executar, ler_exclusoes)
from pipeline.target.workspace import PoolWorktrees  # noqa: E402
from pipeline.validation.runner import ConfigValidacao, validar  # noqa: E402

CATALOGO = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"
BASELINE_SETEMBRO = RAIZ_REPO / "outputs" / "sast_antes" / "baseline_raw.json"
PROJETO = "OWASP Juice Shop v20.1.1"

console = Console()


# --------------------------------------------------------------------------
# Saidas
# --------------------------------------------------------------------------

@dataclass
class Saidas:
    raiz: Path

    def d(self, nome: str) -> Path:
        p = self.raiz / nome
        p.mkdir(parents=True, exist_ok=True)
        return p

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
                        catalogo: list[dict], semgrep_bin: str = "semgrep") -> tuple[list[Finding], dict]:
    """Varre o worktree limpo (ou reaproveita a varredura desta execucao) e
    compara com o baseline de setembro."""
    arq = saidas.baseline_sessao(execucao)
    reutilizada = arq.exists()
    with pool.alugar() as wt:
        if not reutilizada:
            console.log(f"Varredura SAST da sessao em {wt.name} (repositorio inteiro)...")
            inicio = time.monotonic()
            executar(wt, RULESETS, saida_bruta=arq,
                     exclusoes=ler_exclusoes(RAIZ_REPO / "config" / "semgrepignore"), semgrep_bin=semgrep_bin)
            console.log(f"  concluida em {time.monotonic() - inicio:.0f}s -> {rel(arq)}")
        sessao = carregar_resultados(arq, wt)
        setembro = carregar_resultados(BASELINE_SETEMBRO, wt)

    versao_sessao = json.loads(arq.read_text(encoding="utf-8")).get("version")
    versao_set = json.loads(BASELINE_SETEMBRO.read_text(encoding="utf-8")).get("version")
    sig_sessao = {assinatura(f) for f in sessao}
    sig_set = {assinatura(f) for f in setembro}
    elig_sessao = _elegiveis_dedup(sessao)
    sig_catalogo = {c["assinatura"] for c in catalogo if c["elegivel"]}
    nome = {assinatura(f): f"{f.check_id} @ {f.path}" for f in sessao + setembro}
    comparacao = {
        "baseline_setembro": rel(BASELINE_SETEMBRO),
        "baseline_sessao": rel(arq),
        "reutilizada": reutilizada,
        "semgrep_versao": {"setembro": versao_set, "sessao": versao_sessao},
        "achados_brutos": {"setembro": len(setembro), "sessao": len(sessao)},
        "assinaturas_brutas_distintas": {"setembro": len(sig_set), "sessao": len(sig_sessao)},
        "so_no_setembro": sorted(nome[s] for s in sig_set - sig_sessao),
        "so_na_sessao": sorted(nome[s] for s in sig_sessao - sig_set),
        "elegiveis_sessao": len(elig_sessao),
        "casos_do_catalogo_ausentes_na_sessao": sorted(
            c["caso_id"] for c in catalogo if c["elegivel"] and c["assinatura"] not in sig_sessao),
        "elegiveis_novos_na_sessao_fora_do_catalogo": sorted(nome[s] for s in elig_sessao - sig_catalogo),
    }
    comparacao["diverge"] = bool(
        comparacao["so_no_setembro"] or comparacao["so_na_sessao"]
        or len(setembro) != len(sessao) or versao_set != versao_sessao)
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
        self.eventos_llm = []
        self.orcamento_esgotado = False
        self.custo_desconhecido = False
        self.cliente = None
        if not args.dry_run:
            from pipeline.llm.provider import criar_cliente, identidade_offline
            if getattr(args, 'llm_identidade', None) is not None and identidade_offline() != args.llm_identidade:
                raise ValueError('Configuração LLM alterada após o preflight')
            self.cliente = criar_cliente(parar=lambda: self.parar.is_set() or parada_solicitada(args))
            if hasattr(self.cliente, 'conferir_conexao'):
                self.custo_desconhecido = True
                self.cliente.conferir_conexao()

    def somar_custo(self, usd: float) -> float:
        with self.lock_custo:
            self.custo_sessao += usd
            return self.custo_sessao


def tentativa(ctx: Contexto, issue: dict, estrategia: str, wt: Path, tid: str) -> dict:
    s = ctx.saidas
    args = ctx.args
    PoolWorktrees.restaurar(wt)
    amp = getattr(ctx, "ampliado", None)
    if amp:
        from pipeline.catalogo import carregar as validar_catalogo
        from pipeline.execucao_ampliada import conferir_validacao_contrato
        conferir_validacao_contrato(amp,args,wt)
        amp.perfil.conferir()
        if validar_catalogo(amp.catalogo.caminho).hashes != amp.catalogo.hashes:
            raise ValueError('Catálogo alterado após preflight')
    prompt = builder.montar(issue, wt, estrategia)
    if amp:
        from pipeline.execucao_ampliada import conferir_prompt_contrato
        conferir_prompt_contrato(amp,prompt,args.estrategias+args.diagnosticos)
    gravar_json(s.d("prompts") / f"{tid}.json", prompt.to_dict())

    if args.dry_run:
        texto = resposta_falsa_ampliada(issue, wt) if amp else resposta_falsa(issue, wt)
        llm = {"modelo": "dry-run", "seed": None, "system_fingerprint": None, "tokens_entrada": 0,
               "tokens_saida": 0, "latencia_s": 0.0, "custo_usd": 0.0, "do_cache": False,
               "finish_reason": None, "recusa": None, "hash_prompt": prompt.hash_prompt}
    else:
        r = ctx.cliente.gerar(prompt.mensagens)
        from pipeline.llm.provider import texto_aplicavel
        texto = texto_aplicavel(r)
        llm = {k: v for k, v in r.to_dict().items() if k != "conteudo"}
    gravar_json(s.d("respostas_llm") / f"{tid}.json", {"texto": r.conteudo if not args.dry_run else texto, **llm})

    correcao = interpretar(texto)
    fontes_originais = {}
    if amp and not isinstance(correcao, ResultadoAplicacao):
        for ed in correcao.edicoes:
            path = (wt / ed.arquivo).resolve()
            if path.is_relative_to(wt.resolve()) and path.is_file():
                fontes_originais[path.relative_to(wt.resolve()).as_posix()] = path.read_bytes()
    aplic = correcao if isinstance(correcao, ResultadoAplicacao) else aplicar(wt, correcao)

    linha = {
        **({k:llm.get(k) for k in ('provedor','identidade_inferencia','custo_motivo','espera_inferencia_s',
            'custo_api_usd','custo_infraestrutura_usd','requisicao_s','chamadas_enviadas','ambiente_inferencia','endpoint_sha256','estado_geracao','latencia_original_s')}
            if llm.get('provedor') == 'colab' else {}),
        **({'provedor':'openai','identidade_inferencia':getattr(args,'llm_identidade',None)}
            if not args.dry_run and llm.get('provedor') != 'colab' and getattr(args,'llm_identidade',None) else {}),
        "tentativa_id": tid, "execucao": args.execucao, "dry_run": args.dry_run,
        "caso_id": issue["caso_id"], "projeto": PROJETO,
        **({"assinatura_ocorrencia": issue["assinatura_ocorrencia"]} if amp else {"assinatura": issue["assinatura"]}),
        "arquivo": issue["arquivo"], "linha": issue["linha_inicio"], "check_id": issue["check_id"],
        "cwe": issue["cwe"], "owasp_2025": issue["owasp_2025"], "sigla_vuln": issue["sigla_vuln"],
        "modo_regra": issue.get("modo_regra"), "faixa_regra": faixa_regra(issue),
        "estrategia_prompt": prompt.estrategia,
        # desenho = estrategia do TCC 1 (P1-P4); diagnostico = P1L (protocolo, Secao 12)
        "condicao": "diagnostico" if estrategia in builder.DIAGNOSTICOS else "desenho",
        **prompt.metadados_rag(),
        "categoria_rag": issue.get("categoria_rag"),
        "roteiro_status": prompt.roteiro_status, "roteiro_sha256": prompt.roteiro_sha256,
        "modelo": llm["modelo"], "seed": llm["seed"], "system_fingerprint": llm["system_fingerprint"],
        "hash_prompt": prompt.hash_prompt, "do_cache": llm["do_cache"],
        "finish_reason": llm["finish_reason"], "recusa": llm["recusa"],
        "modo_contexto": prompt.modo_contexto,
        "status_aplicacao": aplic.status, "detalhe_aplicacao": aplic.detalhe,
        "aplicador_versao": VERSAO_APLICADOR, "correspondencias_aplicacao": aplic.correspondencias,
        "arquivos_alterados": aplic.arquivos,
        "R": None, "F": None, "M": None, "tier_falha": None,
        "F_sem_separacao": None, "F_marcador": None, "F_criterio": None,
        "tier_falha_sem_separacao": None, "tier_falha_marcador": None, "tier_falha_criterio": None,
        "testes_falhos_d_marcador": [], "testes_falhos_d_criterio": [],
        "testes_falhos_f_marcador": [], "testes_falhos_f_criterio": [],
        "novas_issues_qtd": None, "novas_issues_ids": [],
        "testes_falhos_novos": [], "testes_falhos_intermitentes": [], "reexecucoes": 0,
        "tokens_entrada": llm["tokens_entrada"], "tokens_saida": llm["tokens_saida"],
        "duracao_llm_s": llm["latencia_s"], "duracao_sast_s": None, "duracao_validacao_s": None,
        "custo_usd": llm["custo_usd"], "classificacao_final": None,
        "versao_semgrep": ctx.versao_semgrep, "worktree": wt.name,
        "sast_depois": None, "sast_depois_raw": None,
        "artefatos": {"prompt": rel(s.d("prompts") / f"{tid}.json"),
                      "resposta": rel(s.d("respostas_llm") / f"{tid}.json")},
    }

    if amp:
        linha.update(contrato_execucao_sha256=amp.contrato_hash, hashes_catalogo=amp.catalogo.hashes,
                     perfil_sha256=amp.perfil.hash, classificacao_auditoria=issue['classificacao_auditoria'],
                     desafios=issue['desafios'], origem_caso=issue['origem'], cobertura_funcional='servidor')
        if args.dry_run and texto is None:
            aplic.status = 'dry_run_sem_patch_suportado'
            linha['status_aplicacao'] = aplic.status
    if aplic.status != "aplicado":
        linha["classificacao_final"] = f"nao_aplicada:{aplic.status}"
        for k in ("sem_separacao", "marcador", "criterio"):
            linha[f"classificacao_{k}"] = linha["classificacao_final"]
        return linha

    diff = subprocess.run(["git", "diff"], cwd=wt, capture_output=True, text=True, timeout=60).stdout
    arq_diff = s.d("patches") / f"{tid}.diff"
    arq_diff.write_text(diff, encoding="utf-8")
    for a in aplic.arquivos:
        destino = s.d("codigos_corrigidos") / tid / a
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wt / a, destino)
    linha["artefatos"]["patch"] = rel(arq_diff)

    # SAST depois: so os arquivos tocados (a analise do Semgrep e por arquivo).
    alvos = sorted(set(aplic.arquivos) | {issue["arquivo"]})
    arq_raw = s.d("sast_depois") / f"{tid}_raw.json"
    inicio = time.monotonic()
    if amp:
        from pipeline.validation.engine import medir
        from pipeline.sast.comparacao import chave_caso
        fontes = {a: (fontes_originais[a], (wt / a).read_bytes()) for a in aplic.arquivos}
        depois_scan, comp, v, medicao = medir(
            wt, issue, fontes, amp.scan, amp.perfil, amp.baseline_testes, arq_raw,
            args, ctx.lock_t4, origem={'execucao':args.execucao,'tentativa_id':tid},
            parar=lambda: parada_solicitada(args))
        linha.update(medicao)
        linha['artefatos']['evidencia_funcional'] = rel(arq_raw.with_name(arq_raw.stem+'_evidencia_funcional.json'))
        comp_file = s.d('comparacoes') / f'{tid}.json'
        gravar_json(comp_file, comp)
        linha.update(R=comp['R'], M=comp['M'], comparacao_status=comp['comparacao_status'],
                     comparacao_artefato=rel(comp_file), novas_issues_qtd=comp['novas_issues_qtd'],
                     possiveis_novas_issues_qtd=comp['possiveis_novas_issues_qtd'],
                     novas_issues_ids=comp['novos'], cobertura_sast_limitada=comp['cobertura_limitada'],
                     motivos_indeterminacao=comp.get('motivos_indeterminacao', []),
                     arquivos_inconclusivos_sast=comp['arquivos_inconclusivos'],
                     falhas_contexto_sast=comp.get('falhas_contexto', {}),
                     versao_comparador=comp['versao_comparador'])
        linha['sast_depois'] = [f.to_dict() for f in depois_scan.findings]
        linha['sast_depois_raw'] = rel(arq_raw) if arq_raw.exists() else None
        linha['duracao_sast_s'] = round(medicao['tempos_medicao']['sast_s'], 3)
        linha['artefatos']['comparacao'] = rel(comp_file)
        if arq_raw.exists(): linha['artefatos']['sast_depois'] = rel(arq_raw)
        cfg = ConfigValidacao(lock_t4=ctx.lock_t4, arquivo_linha_de_base=amp.baseline_testes)
    else:
        depois = executar(wt, RULESETS, saida_bruta=arq_raw, caminhos=alvos, semgrep_bin=args.semgrep_bin)
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
    if not amp:
        v = validar(wt, aplic.arquivos, cfg)
    gravar_json(s.d("testes") / f"{tid}.json", v.to_dict())
    linha["artefatos"]["validacao"] = rel(s.d("testes") / f"{tid}.json")
    # F e tier_falha seguem d_criterio (Secao 7.1); as tres versoes vao juntas
    # para a analise de sensibilidade (Secao 13).
    linha["F"] = None if v.passou is None else int(v.passou)
    linha["tier_falha"] = v.tier_falha
    for k in ("sem_separacao", "marcador", "criterio"):
        valor_f = getattr(v, f"F_{k}")
        linha[f"F_{k}"] = None if valor_f is None else int(valor_f)
        linha[f"tier_falha_{k}"] = getattr(v, f"tier_falha_{k}")
    for k in ("d_marcador", "d_criterio", "f_marcador", "f_criterio"):
        linha[f"testes_falhos_{k}"] = getattr(v, f"testes_falhos_{k}")
    linha["testes_falhos_novos"] = v.testes_falhos_novos
    linha["testes_falhos_intermitentes"] = v.testes_falhos_intermitentes
    linha["reexecucoes"] = v.reexecucoes
    linha["duracao_validacao_s"] = medicao["tempos_medicao"]["validacao_s"] if amp else v.duracao_s
    if amp:
        linha['etapas_validacao'] = medicao['etapas_validacao']
        linha['selecao_testes'] = v.selecao

    for k in ("sem_separacao", "marcador", "criterio"):
        f = linha[f"F_{k}"]
        linha[f"classificacao_{k}"] = ("indeterminada_funcional" if f is None else
                                       "indeterminada_sast" if amp and (linha["R"] is None or linha["M"] is None) else
                                       "aceita" if linha["R"] and f and linha["M"] else
                                       f"rejeitada:R{linha['R']}F{f}M{linha['M']}")
    linha["classificacao_final"] = linha["classificacao_criterio"]
    return linha


# --------------------------------------------------------------------------
# Um caso (estrategias em sequencia)
# --------------------------------------------------------------------------

def nome_tentativa(issue: dict, estrategia: str, execucao: str) -> str:
    return "_".join([issue["caso_id"], issue["owasp_2025"] or "SEMOWASP", issue["sigla_vuln"], estrategia, execucao])


def _aceita_estrita(linha: dict) -> bool:
    return linha.get("classificacao_sem_separacao", linha.get("classificacao_final")) == "aceita"


def parada_solicitada(args) -> bool:
    arquivo = getattr(args, 'arquivo_parada', None)
    return bool(arquivo and Path(arquivo).is_file())


def processar_caso(ctx: Contexto, pool: PoolWorktrees, issue: dict,
                   feitas: dict[str, dict]) -> None:
    """Estrategias do desenho em sequencia, parando na primeira aceita; depois
    as condicoes de diagnostico, que rodam sempre (independem do aceite)."""
    caso = issue["caso_id"]
    pendentes = []
    for e in ctx.args.estrategias:
        tid = nome_tentativa(issue, e, ctx.args.execucao)
        if tid in feitas:
            if _aceita_estrita(feitas[tid]):
                console.log(f"[dim]{caso}: ja aceita em {tid} (retomada), pulando o resto da cadeia[/]")
                pendentes = []
                break
            continue
        pendentes.append((e, tid, True))
    for e in ctx.args.diagnosticos:
        tid = nome_tentativa(issue, e, ctx.args.execucao)
        if tid not in feitas:
            pendentes.append((e, tid, False))
    if not pendentes:
        console.log(f"[dim]{caso}: nada pendente (retomada)[/]")
        return

    cadeia_encerrada = False
    with pool.alugar() as wt:
        for e, tid, na_cadeia in pendentes:
            if ctx.parar.is_set() or parada_solicitada(ctx.args):
                return
            if na_cadeia and cadeia_encerrada:
                continue
            try:
                inicio_tentativa = datetime.now(timezone.utc).isoformat()
                cronometro = time.monotonic()
                linha = tentativa(ctx, issue, e, wt, tid)
                if 'tempos_medicao' in linha:
                    inicio_restauracao = time.monotonic()
                    PoolWorktrees.restaurar(wt)
                    linha['tempos_medicao']['restauracao_s'] = time.monotonic()-inicio_restauracao
                linha['inicio_tentativa'] = inicio_tentativa
                linha['fim_tentativa'] = datetime.now(timezone.utc).isoformat()
                linha['duracao_total_s'] = round(time.monotonic() - cronometro, 3)
            except OrcamentoEsgotado as ex:
                ctx.orcamento_esgotado = True
                ctx.parar.set()
                console.log(f"[bold red]Orcamento esgotado: {ex}. Parando a sessao.[/]")
                return
            except Exception as ex:  # interrompe so este caso; a retomada refaz
                from pipeline.llm.provider import ErroOperacionalLLM, GeracaoCancelada
                if isinstance(ex, ErroOperacionalLLM):
                    ctx.parar.set()
                    evento={'tentativa_id':tid, 'tipo':type(ex).__name__, 'descricao':str(ex)}
                    ctx.eventos_llm.append(evento)
                    with ctx.lock_custo, (ctx.saidas.raiz / 'llm_operacional.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(evento,ensure_ascii=False)+'\n')
                    if isinstance(ex, GeracaoCancelada):return
                ctx.erros.append({"tentativa_id": tid, "erro": f"{type(ex).__name__}: {ex}"})
                console.log(f"[red]{tid}: ERRO {type(ex).__name__}: {ex}. Caso interrompido.[/]")
                return
            amp = getattr(ctx, 'ampliado', None)
            if amp:
                from pipeline.catalogo import digest
                linha['artefatos_sha256'] = {Path(value).relative_to(ctx.saidas.raiz.relative_to(RAIZ_REPO)).as_posix(): digest(RAIZ_REPO / value)
                    for value in linha['artefatos'].values() if (RAIZ_REPO / value).exists()} if ctx.saidas.raiz.is_relative_to(RAIZ_REPO) else {
                    str(Path(value).relative_to(ctx.saidas.raiz)): digest(Path(value)) for value in linha['artefatos'].values() if Path(value).is_absolute() and Path(value).exists()}
            registrar_execucao(linha, wt, ctx.saidas.execucoes, amp.catalogo.commit if amp else None)
            # Resposta do cache nao e cobrada de novo (o custo na linha e o da chamada original).
            if linha['custo_usd'] is None and not linha['do_cache']:
                ctx.custo_desconhecido = True
            total = ctx.somar_custo(0.0 if linha["do_cache"] else (linha["custo_usd"] or 0.0))
            cor = "green" if linha["classificacao_final"] == "aceita" else "yellow"
            console.log(f"[{cor}]{tid}[/] {linha['classificacao_final']} "
                        f"(F sem/marc/crit={linha.get('F_sem_separacao')}/{linha.get('F_marcador')}/{linha.get('F_criterio')}) "
                        f"(aplic={linha['status_aplicacao']}, tier_falha={linha['tier_falha']}, "
                        f"novas={linha['novas_issues_qtd']}) | " +
                        ('custo Colab não informado' if getattr(ctx,'custo_desconhecido',False) else f'US$ sessao {total:.5f}'))
            # A cadeia so para quando a tentativa e aceita sem separacao F/D
            # (definicao mais estrita); assim ha dados para reconstruir a
            # cadeia de cada definicao na analise (Secao 13).
            if na_cadeia and _aceita_estrita(linha):
                cadeia_encerrada = True


# --------------------------------------------------------------------------
# Sessao
# --------------------------------------------------------------------------

def registrar_sessao(saidas: Saidas, execucao: str, info: dict) -> Path:
    """Acrescenta a sessao ao historico da execucao (tambem quando aborta)."""
    arq = saidas.d("resultados_consolidados") / f"{execucao}_sessoes.json"
    historico = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    return gravar_json(arq, historico + [info])


def checar_ambiente(pool: PoolWorktrees, k: int, lock_t4: threading.Lock, baseline_testes: Path | None = None) -> list[dict]:
    """Cenario 1 da F4.3 em cada worktree: sem alteracao, a validacao passa."""
    def um(_):
        with pool.alugar() as wt:
            v = validar(wt, [], ConfigValidacao(lock_t4=lock_t4, **({"arquivo_linha_de_base": baseline_testes} if baseline_testes else {})))
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
    ap.add_argument('--catalogo', type=Path, default=CATALOGO)
    ap.add_argument('--perfil-sast', type=Path)
    ap.add_argument('--saida', type=Path)
    ap.add_argument('--somente-preflight', action='store_true')
    ap.add_argument('--semgrep-bin', default='semgrep')
    ap.add_argument('--baseline-testes', type=Path, default=RAIZ_REPO / 'outputs/baseline_testes.json')
    ap.add_argument('--arquivo-parada', type=Path,
                    help='Controle local: encerrar entre tentativas quando este arquivo existir')
    from pipeline.validation.policy import argumentos, alterada
    argumentos(ap)
    args = ap.parse_args()
    if parada_solicitada(args):
        console.log('Parada solicitada; nenhuma tentativa iniciada.')
        return
    args.estrategias = [e.strip() for e in args.estrategias.split(",") if e.strip()]
    args.diagnosticos = [e.strip() for e in args.diagnosticos.split(",") if e.strip()]
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

    from pipeline.catalogo import carregar as carregar_catalogo
    contexto_catalogo = carregar_catalogo(args.catalogo)
    if not contexto_catalogo.ampliado and alterada(args):
        raise SystemExit("Otimizações de validação requerem catálogo ampliado")
    catalogo = contexto_catalogo.casos
    casos = [c for c in catalogo if c["elegivel"]]
    if args.casos:
        pedidos = [c.strip() for c in args.casos.split(",")]
        desconhecidos = set(pedidos) - {c["caso_id"] for c in casos}
        if desconhecidos:
            raise SystemExit(f"ERRO: casos fora do catalogo elegivel: {sorted(desconhecidos)}")
        casos = [c for c in casos if c["caso_id"] in pedidos]

    ampliado = None
    if contexto_catalogo.ampliado:
        from pipeline.execucao_ampliada import preparar
        ampliado = preparar(args, contexto_catalogo, casos)
        if args.somente_preflight:
            console.log(f'Preflight concluído: {len(casos)} casos; sem chamadas à API.')
            return
    elif args.somente_preflight or args.perfil_sast:
        raise SystemExit('Preflight/perfil local requer catálogo ampliado')
    if parada_solicitada(args):
        console.log('Parada solicitada durante a preparação; nenhuma tentativa iniciada.')
        return
    saidas = Saidas(Path(args.saida).resolve() if args.saida else RAIZ_REPO / "outputs" / ("dry_run" if args.dry_run else ""))
    env = dotenv_values(RAIZ_REPO / ".env")
    pool = PoolWorktrees(RAIZ_REPO / "workspace", k=args.k, commit_esperado=ampliado.catalogo.commit if ampliado else env.get("JUICESHOP_COMMIT"))
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
    if not args.pular_checagem_ambiente and getattr(args,'politica_validacao',None)=='relacionada_v2':
        # O preflight conferiu ambiente e baseline por grupo; não executar suítes amplas.
        sessao_info['checagem_ambiente']={'politica':'relacionada_v2','status':'verificada_no_preflight','testes_executados':False}
    elif not args.pular_checagem_ambiente:
        console.log("Checagem de ambiente: validacao sem alteracao em cada worktree...")
        amb = checar_ambiente(pool, args.k, lock_t4, ampliado.baseline_testes if ampliado else None)
        sessao_info["checagem_ambiente"] = amb
        for a in amb:
            console.log(f"  {a['worktree']}: {'OK' if a['passou'] else 'FALHOU'} ({a['duracao_s']}s)"
                        + (f" intermitentes={a['testes_falhos_intermitentes']}" if a["testes_falhos_intermitentes"] else ""))
        if not all(a["passou"] for a in amb):
            sessao_info["abortada"] = "checagem_ambiente"
            registrar_sessao(saidas, args.execucao, sessao_info)
            raise SystemExit("ERRO: worktree sem alteracao reprovado na validacao. "
                             "Problema de ambiente, nao do pipeline (F4.3).")

    if ampliado:
        sessao = ampliado.scan.findings
        n = len(sessao)
        comp = {'achados_brutos': {'setembro': n, 'sessao': n},
                'semgrep_versao': {'setembro': ampliado.scan.versao, 'sessao': ampliado.scan.versao},
                'diverge': False, 'casos_do_catalogo_ausentes_na_sessao': []}
        sessao_info['contrato_execucao_sha256'] = ampliado.contrato_hash
        sessao_info['commit_alvo'] = ampliado.catalogo.commit
    else:
        sessao, comp = varredura_da_sessao(pool, saidas, args.execucao, catalogo, args.semgrep_bin)
    sessao_info["comparacao_baseline"] = rel(saidas.d("sast_antes") / ("reproducao.json" if ampliado else f"{args.execucao}_comparacao_baseline.json"))
    console.log(f"{'Baseline catálogo' if ampliado else 'Baseline setembro'} x sessão: {comp['achados_brutos']['setembro']} x "
                f"{comp['achados_brutos']['sessao']} achados brutos, "
                f"semgrep {comp['semgrep_versao']['setembro']} x {comp['semgrep_versao']['sessao']}")
    if comp["diverge"]:
        console.log(f"[bold yellow]AVISO: varreduras divergem. So em setembro: {comp['so_no_setembro']}; "
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
    try:
        ctx = Contexto(args, saidas, sessao, versao)
    except Exception as ex:
        from pipeline.llm.provider import ErroOperacionalLLM
        if not isinstance(ex, ErroOperacionalLLM):raise
        evento={'tipo':type(ex).__name__, 'descricao':str(ex), 'etapa':'conexao_antes_das_tentativas'}
        with (saidas.raiz/'llm_operacional.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(evento,ensure_ascii=False)+'\n')
        sessao_info.update(fim=datetime.now(timezone.utc).isoformat(timespec='seconds'),
            custo_usd_sessao=None,erros=[evento],eventos_llm=[evento],inferencia=getattr(args,'llm_identidade',None))
        registrar_sessao(saidas,args.execucao,sessao_info)
        console.log(f'Falha operacional LLM: {ex}')
        sys.exit(1)
    ctx.lock_t4 = lock_t4
    ctx.ampliado = ampliado
    if hasattr(ctx.cliente, 'estado_conexao'):
        evento={'tipo':'conexao_verificada','estado':ctx.cliente.estado_conexao,
                'endpoint_sha256':ctx.cliente.endpoint,'modelo_identidade_sha256':ctx.cliente.cfg.manifesto['identidade_sha256'],
                'ambiente':ctx.cliente.ambiente,'inicio':sessao_info['inicio']}
        ctx.eventos_llm.append(evento)
        with (saidas.raiz/'llm_operacional.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(evento,ensure_ascii=False)+'\n')
    inicio = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.k) as ex:
        list(ex.map(lambda c: processar_caso(ctx, pool, c, feitas), casos))

    sessao_info.update({
        "fim": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "custo_usd_sessao": None if ctx.custo_desconhecido else round(ctx.custo_sessao, 6),
        "inferencia":getattr(args,'llm_identidade',None), 'eventos_llm':ctx.eventos_llm,
        "erros": ctx.erros, "interrompida_por_orcamento": ctx.orcamento_esgotado,
        "interrompida_pelo_usuario": parada_solicitada(args),
    })
    arq_sessoes = registrar_sessao(saidas, args.execucao, sessao_info)

    linhas = [l for l in ler_execucoes(saidas.execucoes) if l.get("execucao") == args.execucao]
    aceitas = {l["caso_id"] for l in linhas if l["classificacao_final"] == "aceita"
               and l.get("condicao", "desenho") == "desenho"}
    console.rule("Resumo")
    console.log(f"{len(linhas)} tentativas registradas, {len(aceitas)} caso(s) com correcao aceita, "
                f"{len(ctx.erros)} erro(s), " + ('custo Colab não informado' if ctx.custo_desconhecido else f'US$ {ctx.custo_sessao:.5f} nesta sessao'))
    console.log(f"Registro: {rel(saidas.execucoes)} | sessao: {rel(arq_sessoes)}")
    if ctx.erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
