#!/usr/bin/env python3
"""F4.3 -- confere o runner de validacao em 3 cenarios controlados.

1. Sem alteracao             -> esperado: passa (T0, T2, T3 ok)
2. Erro de sintaxe proposital -> esperado: falha em T0
3. Quebra de comportamento    -> esperado: T0 passa, falha em T2

Usa routes/keyServer.ts, que tem teste correspondente
(test/server/keyServer.unit.test.ts). O worktree e restaurado ao final de
cada cenario pelo proprio pool.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "src"))
from pipeline.caminhos import rel  # noqa: E402
from pipeline.target.workspace import PoolWorktrees  # noqa: E402
from pipeline.validation.runner import ConfigValidacao, validar  # noqa: E402

ARQUIVO_ALVO = "routes/keyServer.ts"

# Trecho original e a alteracao que mantem os tipos mas muda o comportamento:
# o teste 'should serve requested file' espera 'encryptionkeys/test.file'.
TRECHO_ORIGINAL = "res.sendFile(path.resolve('encryptionkeys/', file))"
TRECHO_QUEBRADO = "res.sendFile(path.resolve('encryptionkeys/', 'outro.arquivo'))"


def ler_env(caminho: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                k, v = linha.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def sem_alteracao(wt: Path) -> None:
    pass


def erro_sintaxe(wt: Path) -> None:
    alvo = wt / ARQUIVO_ALVO
    alvo.write_text(alvo.read_text(encoding="utf-8") + "\nconst quebrado = ;\n", encoding="utf-8")


def quebra_comportamento(wt: Path) -> None:
    alvo = wt / ARQUIVO_ALVO
    texto = alvo.read_text(encoding="utf-8")
    if TRECHO_ORIGINAL not in texto:
        raise RuntimeError(f"Trecho original nao encontrado em {alvo}")
    alvo.write_text(texto.replace(TRECHO_ORIGINAL, TRECHO_QUEBRADO), encoding="utf-8")


# (nome, funcao que altera o worktree, arquivos alterados, passou esperado, tier_falha esperado)
CENARIOS = [
    ("1_sem_alteracao", sem_alteracao, [ARQUIVO_ALVO], True, None),
    ("2_erro_sintaxe", erro_sintaxe, [ARQUIVO_ALVO], False, "T0"),
    ("3_quebra_comportamento", quebra_comportamento, [ARQUIVO_ALVO], False, "T2"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=str(RAIZ_REPO / "workspace"))
    ap.add_argument("--k", type=int, default=1, help="quantos worktrees do pool carregar")
    args = ap.parse_args()

    commit = ler_env(RAIZ_REPO / ".env").get("JUICESHOP_COMMIT")
    pool = PoolWorktrees(Path(args.raiz), k=args.k, commit_esperado=commit)
    cfg = ConfigValidacao()

    registros = []
    for nome, alterar, arquivos, passou_esp, tier_esp in CENARIOS:
        with pool.alugar() as wt:
            print(f"\n[{nome}] em {wt.name}")
            alterar(wt)
            r = validar(wt, arquivos, cfg)
        limpo = PoolWorktrees.esta_limpo(wt)

        ok = (r.passou == passou_esp) and (r.tier_falha == tier_esp)
        for t in r.tiers:
            print(f"  {t.tier}: {'OK' if t.passou else 'FALHOU'} em {t.duracao_s}s"
                  + (f" ({t.motivo})" if t.motivo else ""))
        if r.t2_pulado:
            print("  T2: pulado (sem teste correspondente)")
        print(f"  esperado: passou={passou_esp}, tier_falha={tier_esp}")
        print(f"  obtido:   passou={r.passou}, tier_falha={r.tier_falha}  -> {'CONFERE' if ok else 'DIVERGE'}")
        print(f"  worktree restaurado: {'sim' if limpo else 'NAO'}")
        if not ok:
            ultimo = r.tiers[-1]
            print(f"  saida de {ultimo.tier} (final):\n{ultimo.saida[-1500:]}")

        registros.append({
            "cenario": nome, "worktree": wt.name,
            "esperado": {"passou": passou_esp, "tier_falha": tier_esp},
            "obtido": r.to_dict(), "confere": ok, "worktree_restaurado": limpo,
        })

    saida = RAIZ_REPO / "outputs" / "validacao_cenarios" / "cenarios_f4.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_alvo": commit,
        "config": {k: rel(v) if isinstance(v, Path) else v for k, v in cfg.__dict__.items()},
        "cenarios": registros,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    total_ok = sum(r["confere"] and r["worktree_restaurado"] for r in registros)
    print(f"\n{total_ok}/{len(registros)} cenarios conferem. Detalhes em {saida.relative_to(RAIZ_REPO)}")
    sys.exit(0 if total_ok == len(registros) else 1)


if __name__ == "__main__":
    main()
