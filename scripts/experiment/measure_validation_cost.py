#!/usr/bin/env python3
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402


import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

# Sincroniza o timezone do processo com UTC, para que os testes do Juice Shop fiquem consistentes
os.environ["TZ"] = "UTC"

# T2 e T5 precisam de um arquivo real -- os testes escolhidos abaixo sao placeholders de exemplo.
CMD_T0 = ["npx", "tsc", "--noEmit"]
CMD_T2 = ["node", "--import", "./test/server/helpers/test-env.mjs", "--import", "tsx",
          "--test", "--test-force-exit", "test/server/b2bOrder.unit.test.ts"]
CMD_T3 = ["npm", "run", "test:server"]
CMD_T4 = ["npm", "run", "test:api"]
CMD_T5 = ["npx", "cypress", "run", "--spec",
          "test/cypress/e2e/b2bOrder.spec.ts"]

PORTA_SERVIDOR = 3000
URL_SAUDE = f"http://localhost:{PORTA_SERVIDOR}/"
TIMEOUT_SUBIDA_S = 60
TIMEOUT_COMANDO_S = 1800  # 30 min -- ajuste se a suite completa demorar mais


def cronometrar(cmd: list[str], cwd: Path) -> tuple[bool, float, str]:
    """Roda um comando, cronometra, devolve (passou, duracao_s, saida_resumida)."""
    inicio = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, timeout=TIMEOUT_COMANDO_S,
            capture_output=True, text=True,
        )
        duracao = time.monotonic() - inicio
        saida = (proc.stdout[-500:] + proc.stderr[-500:])
        return proc.returncode == 0, duracao, saida
    except subprocess.TimeoutExpired:
        return False, time.monotonic() - inicio, f"TIMEOUT apos {TIMEOUT_COMANDO_S}s"
    except FileNotFoundError as e:
        return False, 0.0, f"comando nao encontrado: {e}"


def subir_servidor(cwd: Path) -> subprocess.Popen:
    """Sobe 'npm start' em segundo plano e espera responder antes de devolver."""
    proc = subprocess.Popen(
        ["npm", "start"], cwd=cwd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    inicio = time.monotonic()
    while time.monotonic() - inicio < TIMEOUT_SUBIDA_S:
        try:
            urllib.request.urlopen(URL_SAUDE, timeout=2)
            return proc
        except Exception:
            time.sleep(1)
    proc.terminate()
    raise RuntimeError(f"Servidor nao respondeu em {URL_SAUDE} apos {TIMEOUT_SUBIDA_S}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", default="workspace/wt-1")
    args = ap.parse_args()

    wt = Path(args.worktree).resolve()
    if not wt.is_dir():
        raise SystemExit(f"Worktree nao encontrado: {wt}. Rode setup_target.sh primeiro.")

    resultados: dict[str, dict] = {}
    print(f"Medindo custos de validacao em {wt}\n")

    for tier, cmd in [("T0_compilacao", CMD_T0),
                       ("T2_arquivo_unico", CMD_T2),
                       ("T3_suite_unitaria", CMD_T3),
                       ("T4_api", CMD_T4)]:
        print(f"[{tier}] rodando: {' '.join(cmd)}")
        passou, duracao, saida = cronometrar(cmd, wt)
        resultados[tier] = {"comando": cmd, "passou": passou, "duracao_s": round(duracao, 1)}
        print(f"  -> {'OK' if passou else 'FALHOU'} em {duracao:.1f}s")
        if not passou:
            print(f"  saida (ultimas linhas):\n{saida}\n")

    # T5 precisa servidor de verdade no ar.
    print("\nSubindo o servidor para T5...")
    servidor = subir_servidor(wt)
    try:
        for tier, cmd in [("T5_desafio_cypress", CMD_T5)]:
            print(f"[{tier}] rodando: {' '.join(cmd)}")
            passou, duracao, saida = cronometrar(cmd, wt)
            resultados[tier] = {"comando": cmd, "passou": passou, "duracao_s": round(duracao, 1)}
            print(f"  -> {'OK' if passou else 'FALHOU'} em {duracao:.1f}s")
            if not passou:
                print(f"  saida (ultimas linhas):\n{saida}\n")
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)

    saida_json = Path("outputs/custos_validacao") / f"{wt.name}.json"
    saida_json.parent.mkdir(parents=True, exist_ok=True)
    saida_json.write_text(json.dumps(resultados, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("Resumo -- cole isto no caderno de laboratorio (F2.4):\n")
    for tier, r in resultados.items():
        print(f"{tier}: {r['duracao_s']}s ({'passou' if r['passou'] else 'FALHOU'})")
    print(f"\nDetalhes salvos em {saida_json}")


if __name__ == "__main__":
    main()