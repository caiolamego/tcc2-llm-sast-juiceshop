"""Arquiva teste de integracao local da rodada 9, sem sobrescrever evidencias."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "scripts/test_rodada9_flows.mjs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    if args.saida.exists():
        parser.error("Evidencias ja existem; escolha um diretorio novo")
    env = {**os.environ, "JUICE_SHOP_WORKTREE": str(args.worktree.resolve()), "ROUND9_DEPS": str(args.deps.resolve())}
    cmd = ["node", "--test", "--test-reporter=tap", str(TEST)]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    args.saida.mkdir(parents=True)
    (args.saida / "testes.tap").write_text(result.stdout + result.stderr, encoding="utf-8")
    deps_out = args.saida / "dependencias"
    deps_out.mkdir()
    for name in ("package.json", "package-lock.json"):
        (deps_out / name).write_bytes((args.deps / name).read_bytes())
    sources = ["server.ts", "models/product.ts", "routes/dataErasure.ts", "routes/verify.ts",
               "lib/insecurity.ts", "views/dataErasureResult.hbs", "package.json"]
    metadata = {
        "comando": cmd, "exit_code": result.returncode,
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "commit_alvo": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.worktree, text=True).strip(),
        "teste_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256((deps_out / "package-lock.json").read_bytes()).hexdigest(),
        "fontes_sha256": {p: hashlib.sha256((args.worktree / p).read_bytes()).hexdigest() for p in sources},
        "limites": "Integracao reduzida: Express/Finale/SQLite/hbs e JWT guard reais; sessao dataErasure, privacy model e hooks de desafios simulados. Nao E2E completo."
    }
    (args.saida / "manifesto.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
