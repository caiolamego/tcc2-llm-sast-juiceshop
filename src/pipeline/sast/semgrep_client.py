"""Execucao e normalizacao dos resultados do Semgrep."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    check_id: str
    path: str
    start_line: int
    end_line: int
    severity: str
    message: str
    cwe: tuple[str, ...]
    owasp: tuple[str, ...]
    category: str
    code: str
    fingerprint: str

    def to_dict(self) -> dict:
        return asdict(self)


def _normalizar(codigo: str) -> str:
    """Remove ruido de formatacao para gerar assinatura estavel."""
    sem_comentarios = re.sub(r"//.*?$|/\*.*?\*/", "", codigo, flags=re.S | re.M)
    return re.sub(r"\s+", " ", sem_comentarios).strip()


def assinatura(f: Finding) -> str:
    """Chave estavel de comparacao antes/depois (D6)."""
    if f.fingerprint:
        return f"fp:{f.fingerprint}"
    bruto = f"{f.check_id}|{f.path}|{_normalizar(f.code)}"
    return "hash:" + hashlib.sha256(bruto.encode()).hexdigest()[:16]


def ler_exclusoes(caminho: Path) -> list[str]:
    """Le config/semgrepignore, ignorando linhas em branco e comentarios (#)."""
    if not caminho.exists():
        return []
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in linhas if l.strip() and not l.strip().startswith("#")]


def executar(
    alvo: Path,
    rulesets: list[str],
    saida_bruta: Path | None = None,
    exclusoes: list[str] | None = None,
) -> list[Finding]:
    """exclusoes: padroes tipo .gitignore, normalmente lidos de config/semgrepignore
    via ler_exclusoes(). NAO existe flag '--exclude-rule-file' no Semgrep -- cada
    padrao vira uma flag '--exclude' separada (confirmado em F3.2)."""
    cmd = ["semgrep", "--json", "--metrics=off", "--no-git-ignore"]
    for r in rulesets:
        cmd += ["--config", r]
    for padrao in (exclusoes or []):
        cmd += ["--exclude", padrao]
    cmd.append(str(alvo))

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=alvo)
    # Semgrep usa codigo 1 quando encontra findings; so >1 e erro real.
    if proc.returncode > 1:
        raise RuntimeError(f"Semgrep falhou ({proc.returncode}): {proc.stderr[:800]}")

    dados = json.loads(proc.stdout)
    if saida_bruta:
        saida_bruta.parent.mkdir(parents=True, exist_ok=True)
        saida_bruta.write_text(json.dumps(dados, indent=2))

    return [_parse(r, alvo) for r in dados.get("results", [])]


def carregar_resultados(caminho_json: Path, raiz: Path) -> list[Finding]:
    """Carrega findings de um JSON bruto JA GERADO (ex.: outputs/sast_antes/
    baseline_raw.json de F3.2) -- NAO executa o semgrep de novo. Usado por
    scripts/build_issue_catalog.py (F3.4), que trabalha em cima do baseline
    ja rodado, e nao precisa (nem deve) re-escanear."""
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
    return [_parse(r, raiz) for r in dados.get("results", [])]


def _parse(r: dict, raiz: Path) -> Finding:
    extra = r.get("extra", {})
    meta = extra.get("metadata", {})
    try:
        caminho = str(Path(r["path"]).resolve().relative_to(raiz.resolve()))
    except ValueError:
        caminho = r["path"]
    return Finding(
        check_id=r["check_id"],
        path=caminho,
        start_line=r["start"]["line"],
        end_line=r["end"]["line"],
        severity=extra.get("severity", ""),
        message=extra.get("message", ""),
        cwe=tuple(meta.get("cwe", []) or []),
        owasp=tuple(meta.get("owasp", []) or []),
        category=meta.get("category", ""),
        code=extra.get("lines", ""),
        fingerprint=extra.get("fingerprint", ""),
    )