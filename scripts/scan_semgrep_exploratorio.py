#!/usr/bin/env python3
"""Roda perfis exploratorios sem alterar o baseline ou o catalogo oficial.

Exemplo:
    python3 scripts/scan_semgrep_exploratorio.py --worktree workspace/wt-1
    python3 scripts/audit_semgrep_coverage.py \
        outputs/sast_antes/baseline_raw.json \
        outputs/auditoria_sast/default.json \
        outputs/auditoria_sast/security-audit.json \
        outputs/auditoria_sast/angular-sanitizer-bypass.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
BASELINE_META = RAIZ / "outputs/sast_antes/catalogo_meta.json"
EXCLUSOES = RAIZ / "config/semgrepignore"
SAIDA = RAIZ / "outputs/auditoria_sast"
PERFIS = {
    "default": ["p/default"],
    "security-audit": ["p/security-audit"],
    "angular-sanitizer-bypass": [str(RAIZ / "rules/rodada1/angular-sanitizer-bypass.yaml")],
    "custom-rules": [str(RAIZ / f"rules/rodada1/{nome}.yaml") for nome in
                     ("angular-sanitizer-bypass", "mongodb-untrusted-multi-update",
                      "redirect-substring-allowlist")],
    "rodada2": [str(RAIZ / "rules/rodada2")],
    "rodada3": [str(RAIZ / "rules/rodada3")],
    "rodada4": [str(RAIZ / "rules/rodada4")],
    "rodada5": [str(RAIZ / "rules/rodada5")],
    "rodada6": [str(RAIZ / "rules/rodada6")],
    "rodada7": [str(RAIZ / "rules/rodada7")],
    "rodada8": [str(RAIZ / "rules/rodada8")],
    "rodada9": [str(RAIZ / "rules/rodada9")],
    "rodada10": [str(RAIZ / "rules/rodada10")],
    "rodada11": [str(RAIZ / "rules/rodada11")],
    "rodada12": [str(RAIZ / "rules/rodada12")],
}


def executar(cmd: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, default=RAIZ / "workspace/wt-1")
    parser.add_argument("--semgrep-bin", default="semgrep")
    parser.add_argument("--saida", type=Path, default=SAIDA,
                        help="Diretorio novo para repetir o scan sem sobrescrever artefatos")
    parser.add_argument("--allow-version-drift", action="store_true")
    parser.add_argument("--timeout", type=int,
                        help="Limite em segundos por regra/arquivo; registrado no manifesto")
    parser.add_argument("--perfis", nargs="+", choices=PERFIS, default=list(PERFIS))
    args = parser.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout deve ser positivo")
    wt = args.worktree.resolve()
    if not wt.is_dir():
        parser.error(f"alvo ausente: {wt}")

    commit = executar(["git", "rev-parse", "HEAD"], wt)
    if commit.returncode != 0:
        parser.error(f"nao foi possivel conferir o commit em {wt}")
    meta = json.loads(BASELINE_META.read_text(encoding="utf-8"))
    esperado = meta["commit_alvo"]
    if commit.stdout.strip() != esperado:
        parser.error(f"commit {commit.stdout.strip()} difere do baseline {esperado}")

    versao = executar([args.semgrep_bin, "--version"], wt)
    if versao.returncode != 0:
        parser.error(f"Semgrep indisponivel: {versao.stderr.strip()}")
    versao = versao.stdout.strip().splitlines()[-1]
    if versao != meta["semgrep_versao"] and not args.allow_version_drift:
        parser.error(f"Semgrep {versao} difere do baseline {meta['semgrep_versao']}; "
                     "use --allow-version-drift apenas para um estudo separado de versoes")
    exclusoes = [linha.strip() for linha in EXCLUSOES.read_text(encoding="utf-8").splitlines()
                if linha.strip() and not linha.lstrip().startswith("#")]
    destino_dir = args.saida.resolve()
    destino_dir.mkdir(parents=True, exist_ok=True)
    rodada = args.perfis[0] if len(args.perfis) == 1 and args.perfis[0].startswith("rodada") else None
    if rodada and any(p.exists() for p in
                      (destino_dir / f"{rodada}.json", destino_dir / f"manifesto-{rodada}.json")):
        parser.error(f"artefatos da {rodada} ja existem; nao sobrescrever o historico")

    for nome in args.perfis:
        destino = destino_dir / f"{nome}.json"
        cmd = [args.semgrep_bin, "scan", "--json", "--metrics=off", "--no-git-ignore"]
        if args.timeout is not None:
            cmd.extend(["--timeout", str(args.timeout)])
        for perfil in PERFIS[nome]:
            cmd.extend(["--config", perfil])
        if nome in {"angular-sanitizer-bypass", "custom-rules"} or nome.startswith("rodada"):
            # Sem isso, Semgrep prefixa o ID da regra com o caminho absoluto
            # deste repositorio, tornando check_id dependente da maquina.
            cmd.append("--no-rewrite-rule-ids")
        for padrao in exclusoes:
            cmd.extend(["--exclude", padrao])
        cmd.extend(["--output", str(destino), "."])
        resultado = executar(cmd, wt)
        if resultado.returncode not in (0, 1) or not destino.exists():
            raise RuntimeError(f"{nome}: Semgrep falhou ({resultado.returncode}): "
                               f"{resultado.stderr[-2000:]}")
        dados = json.loads(destino.read_text(encoding="utf-8"))
        if "results" not in dados:
            raise RuntimeError(f"{nome}: JSON sem results; veja {destino}")
        print(f"{nome}: {len(dados['results'])} ocorrencias, {len(dados.get('errors', []))} avisos "
              f"-> {destino}")

    manifesto = {
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_alvo": esperado,
        "semgrep_versao": versao,
        "perfis": args.perfis,
        "exclusoes": exclusoes,
        "nota": "Scans exploratorios; nao alteram o catalogo oficial do experimento.",
    }
    if args.timeout is not None:
        manifesto["timeout_por_regra_segundos"] = args.timeout
    if rodada:
        manifesto["regras_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((RAIZ / f"rules/{rodada}").glob("*.yaml"))
        }
        manifesto["scan_sha256"] = hashlib.sha256((destino_dir / f"{rodada}.json").read_bytes()).hexdigest()
        caminho_manifesto = destino_dir / f"manifesto-{rodada}.json"
    else:
        caminho_manifesto = destino_dir / "manifesto.json"
    caminho_manifesto.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
