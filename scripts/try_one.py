#!/usr/bin/env python3
"""Uma tentativa ponta a ponta sobre um caso do catalogo (criterio da F5).

catalogo -> prompt -> LLM (ou resposta falsa com --dry-run) -> patch no
worktree alugado -> validacao em camadas -> git diff + resultado.

Artefatos (D7): outputs/tentativas/<CASO>_<OWASP>_<VULN>_<PROMPT>_<EXECUCAO>_<ARTEFATO>.<ext>
Com --dry-run vao para outputs/tentativas/dry_run/, para nao misturar com
tentativas reais.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "src"))
from dotenv import dotenv_values  # noqa: E402

from pipeline.llm.schema import Correcao, Edicao  # noqa: E402
from pipeline.patching.applier import ResultadoAplicacao, aplicar, interpretar  # noqa: E402
from pipeline.prompts.builder import montar  # noqa: E402
from pipeline.target.workspace import PoolWorktrees  # noqa: E402
from pipeline.validation.runner import ConfigValidacao, validar  # noqa: E402

CATALOGO = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"
DIR_SAIDA = RAIZ_REPO / "outputs" / "tentativas"


def resposta_falsa(issue: dict, wt: Path) -> str:
    """Edicao inofensiva: acrescenta um comentario no fim da linha do finding.
    Exercita applier e validacao sem chamar a API."""
    linhas = (wt / issue["arquivo"]).read_text(encoding="utf-8").splitlines()
    linha = linhas[issue["linha_inicio"] - 1]
    c = Correcao(
        vulnerabilidade_identificada="[dry-run]",
        causa_da_vulnerabilidade="[dry-run]",
        estrategia_de_correcao="[dry-run] comentario inofensivo",
        edicoes=[Edicao(arquivo=issue["arquivo"], trecho_original=linha,
                        trecho_corrigido=linha + " // dry-run")],
        justificativa_tecnica="[dry-run]",
        limitacoes_da_correcao="[dry-run]",
    )
    return c.model_dump_json()


def salvar(base: Path, artefato: str, conteudo, ext: str = "json") -> Path:
    arq = base.parent / f"{base.name}_{artefato}.{ext}"
    if ext == "json":
        conteudo = json.dumps(conteudo, indent=2, ensure_ascii=False)
    arq.write_text(conteudo, encoding="utf-8")
    return arq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", required=True, help="ex.: JS003")
    ap.add_argument("--estrategia", default="P1")
    ap.add_argument("--execucao", default="E01")
    ap.add_argument("--dry-run", action="store_true", help="resposta falsa, sem chamar a API")
    ap.add_argument("--sem-t4", action="store_true", help="pula o T4 (testes de API)")
    args = ap.parse_args()

    issue = next((i for i in json.loads(CATALOGO.read_text(encoding="utf-8"))
                  if i["caso_id"] == args.caso), None)
    if issue is None:
        raise SystemExit(f"Caso {args.caso} nao esta em {CATALOGO}")
    if not issue.get("elegivel"):
        raise SystemExit(f"Caso {args.caso} nao e elegivel ({issue.get('motivo_exclusao')})")

    nome = "_".join([issue["caso_id"], issue["owasp_2025"], issue["sigla_vuln"],
                     args.estrategia, args.execucao])
    pasta = DIR_SAIDA / "dry_run" if args.dry_run else DIR_SAIDA
    pasta.mkdir(parents=True, exist_ok=True)
    base = pasta / nome

    env = dotenv_values(RAIZ_REPO / ".env")
    pool = PoolWorktrees(RAIZ_REPO / "workspace", k=1, commit_esperado=env.get("JUICESHOP_COMMIT"))
    cfg_val = ConfigValidacao(rodar_t4=not args.sem_t4)

    resumo: dict = {
        "nome": nome, "caso": issue["caso_id"], "check_id": issue["check_id"],
        "arquivo": issue["arquivo"], "linha": issue["linha_inicio"],
        "commit_alvo": env.get("JUICESHOP_COMMIT"), "dry_run": args.dry_run,
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    with pool.alugar() as wt:
        resumo["worktree"] = wt.name
        prompt = montar(issue, wt, args.estrategia)
        salvar(base, "prompt", prompt.to_dict())
        resumo["prompt"] = {"estrategia": prompt.estrategia, "modo_contexto": prompt.modo_contexto,
                            "linhas_contexto": [prompt.linha_ini_contexto, prompt.linha_fim_contexto],
                            "hash_prompt": prompt.hash_prompt}
        print(f"[{nome}] {issue['arquivo']}:{issue['linha_inicio']} em {wt.name}")
        print(f"  prompt: {prompt.estrategia}, {prompt.modo_contexto} "
              f"(linhas {prompt.linha_ini_contexto}-{prompt.linha_fim_contexto})")

        if args.dry_run:
            texto = resposta_falsa(issue, wt)
            resumo["llm"] = {"dry_run": True}
        else:
            from pipeline.llm.openai_client import ClienteLLM, ConfigLLM
            r = ClienteLLM(ConfigLLM.do_env()).gerar(prompt.mensagens)
            texto = r.conteudo
            resumo["llm"] = {k: v for k, v in r.to_dict().items() if k != "conteudo"}
            print(f"  llm: {r.modelo}, fingerprint={r.system_fingerprint}, "
                  f"{r.tokens_entrada}+{r.tokens_saida} tokens, {r.latencia_s}s, "
                  f"US$ {r.custo_usd:.5f}{' (cache)' if r.do_cache else ''}")
        salvar(base, "resposta", {"texto": texto})

        correcao = interpretar(texto)
        if isinstance(correcao, ResultadoAplicacao):
            aplic = correcao
        else:
            aplic = aplicar(wt, correcao)
        resumo["aplicacao"] = aplic.__dict__
        print(f"  aplicacao: {aplic.status} {aplic.detalhe}".rstrip())

        if aplic.status == "aplicado":
            diff = subprocess.run(["git", "diff"], cwd=wt, capture_output=True,
                                  text=True, timeout=60).stdout
            salvar(base, "patch", diff, ext="diff")
            print("\n----- git diff -----\n" + diff + "--------------------\n")
            v = validar(wt, aplic.arquivos, cfg_val)
            salvar(base, "validacao", v.to_dict())
            resumo["validacao"] = {"passou": v.passou, "tier_falha": v.tier_falha,
                                   "duracao_s": v.duracao_s,
                                   "tiers": {t.tier: t.passou for t in v.tiers}}
            for t in v.tiers:
                print(f"  {t.tier}: {'OK' if t.passou else 'FALHOU'} em {t.duracao_s}s"
                      + (f" ({t.motivo})" if t.motivo else ""))
            print(f"  validacao: passou={v.passou}, tier_falha={v.tier_falha}")

    arq = salvar(base, "resumo", resumo)
    print(f"\nArtefatos em {pasta.relative_to(RAIZ_REPO)}/ ({arq.name} e vizinhos)")


if __name__ == "__main__":
    main()
