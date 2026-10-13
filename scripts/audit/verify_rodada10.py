"""Arquiva testes isolados, lockfile e hashes sem sobrescrever evidencias."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = RAIZ_REPO
TEST = ROOT / "tests/integration/rodada10/test.mjs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    if args.saida.exists():
        parser.error("Evidencias ja existem; escolha um diretorio novo")
    env = {**os.environ, "JUICE_SHOP_WORKTREE": str(args.worktree.resolve()), "ROUND10_DEPS": str(args.deps.resolve())}
    cmd = ["node", "--test", "--test-reporter=tap", str(TEST)]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    args.saida.mkdir(parents=True)
    (args.saida / "testes.tap").write_text(result.stdout + result.stderr, encoding="utf-8")
    deps_out = args.saida / "dependencias"
    deps_out.mkdir()
    for name in ("package.json", "package-lock.json"):
        (deps_out / name).write_bytes((args.deps / name).read_bytes())
    sources = ["server.ts", "routes/order.ts", "routes/coupon.ts", "lib/insecurity.ts", "lib/utils.ts", "package.json"]
    metadata = {
        "comando": cmd, "exit_code": result.returncode,
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "commit_alvo": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.worktree, text=True).strip(),
        "teste_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256((deps_out / "package-lock.json").read_bytes()).hexdigest(),
        "fontes_sha256": {p: hashlib.sha256((args.worktree / p).read_bytes()).hexdigest() for p in sources},
        "limites": "Testes isolados das funcoes e trecho de calculo reais com z85 real; cesta/PDF/hooks simulados, relogio fixo. Nao HTTP, checkout completo nem pagamento real."
    }
    (args.saida / "manifesto.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
