"""Arquiva teste local da rodada 11 e dependencias; recusa sobrescrita."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "scripts/test_rodada11_flows.mjs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    if args.saida.exists():
        parser.error("Evidencias ja existem; escolha novo diretorio")
    env = {**os.environ, "JUICE_SHOP_WORKTREE": str(args.worktree.resolve()), "ROUND11_DEPS": str(args.deps.resolve())}
    cmd = ["node", "--test", "--test-reporter=tap", str(TEST)]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    args.saida.mkdir(parents=True)
    (args.saida / "testes.tap").write_text(result.stdout + result.stderr, encoding="utf-8")
    depout = args.saida / "dependencias"
    depout.mkdir()
    for name in ("package.json", "package-lock.json"):
        (depout / name).write_bytes((args.deps / name).read_bytes())
    sources = ["server.ts", "routes/currentUser.ts", "routes/likeProductReviews.ts", "lib/insecurity.ts", "data/mongodb.ts", "package.json"]
    metadata = {
        "comando": cmd, "exit_code": result.returncode,
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "commit_alvo": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.worktree, text=True).strip(),
        "teste_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256((depout / "package-lock.json").read_bytes()).hexdigest(),
        "fontes_sha256": {p: hashlib.sha256((args.worktree / p).read_bytes()).hexdigest() for p in sources},
        "browser": "Chromium 121.0.6167.57 via Playwright 1.41.2 (versao efetiva tambem no TAP)",
        "limites": "Rotas reais e MarsDB/Express/browser reais; identidade e verificacao JWT simuladas. JSONP confirmado somente entre origens do mesmo site, nao cross-site com cookie Lax. Nao login E2E."
    }
    (args.saida / "manifesto.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
