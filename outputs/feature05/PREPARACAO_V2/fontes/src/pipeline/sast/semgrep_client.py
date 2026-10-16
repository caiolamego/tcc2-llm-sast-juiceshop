"""Execucao e normalizacao dos resultados do Semgrep."""
from __future__ import annotations

import hashlib
import json
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
    subcategory: tuple[str, ...] = ()
    start_col: int | None = None
    end_col: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Rulesets do protocolo (Secao 2). Nao versionados pelo registro (D2).
RULESETS = ["p/javascript", "p/typescript", "p/nodejs", "p/expressjs", "p/owasp-top-ten"]
TIMEOUT_SEMGREP_S = 900

# Sem login, o Semgrep devolve este texto no lugar de extra.fingerprint e de
# extra.lines (caderno, 2026-10-07). Tratado como campo ausente.
SENTINELA_SEM_LOGIN = "requires login"


def assinatura(f: Finding) -> str:
    """Chave estavel de comparacao antes/depois (D6): sha256(check_id|caminho).

    Decisao do grupo (2026-10-07): nao depende do fingerprint (ausente sem
    login) nem do codigo (que a propria correcao altera). Coerente com a
    deduplicacao por (check_id, path) do protocolo (passo 5).
    """
    bruto = f"{f.check_id}|{f.path}"
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _sem_sentinela(valor: str) -> str:
    return "" if valor.strip() == SENTINELA_SEM_LOGIN else valor


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
    caminhos: list[str] | None = None,
    semgrep_bin: str = "semgrep",
) -> list[Finding]:
    """exclusoes: padroes tipo .gitignore, normalmente lidos de config/semgrepignore
    via ler_exclusoes(). NAO existe flag '--exclude-rule-file' no Semgrep -- cada
    padrao vira uma flag '--exclude' separada (confirmado em F3.2).
    caminhos: arquivos relativos a 'alvo' para varrer so eles (padrao: tudo)."""
    executable = str(Path(semgrep_bin).resolve()) if "/" in semgrep_bin else semgrep_bin
    cmd = [executable, "--json", "--metrics=off", "--no-git-ignore"]
    for r in rulesets:
        cmd += ["--config", r]
    for padrao in (exclusoes or []):
        cmd += ["--exclude", padrao]
    cmd += caminhos if caminhos else ["."]

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=alvo,
                          timeout=TIMEOUT_SEMGREP_S)
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
    bruto = Path(r["path"])
    # Caminho relativo vem relativo ao cwd do semgrep (a raiz varrida).
    absoluto = bruto if bruto.is_absolute() else raiz / bruto
    try:
        caminho = absoluto.resolve().relative_to(raiz.resolve()).as_posix()
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
        code=_sem_sentinela(extra.get("lines", "")),
        fingerprint=_sem_sentinela(extra.get("fingerprint", "")),
        subcategory=tuple(meta.get("subcategory", []) or []),
        start_col=r["start"].get("col"), end_col=r["end"].get("col"),
        start_offset=r["start"].get("offset"), end_offset=r["end"].get("offset"),
    )

@dataclass
class ScanResultado:
    findings: list[Finding]
    diagnosticos: list[dict]
    versao: str
    falha_operacional: str | None = None


def carregar_scan_perfil(path: Path, alvo: Path, perfil) -> ScanResultado:
    dados = json.loads(path.read_text())
    ids = set(perfil.dados['id_regras'])
    encontrados = []
    for r in dados.get('results', []):
        f = _parse(r, alvo)
        p = Path(f.path)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError(f'Caminho do finding fora do alvo: {f.path}')
        if f.check_id not in ids:
            raise ValueError(f'ID não declarado no perfil: {f.check_id}')
        if None in (f.start_col, f.end_col) or (f.start_line,f.start_col) > (f.end_line,f.end_col):
            raise ValueError('Finding com coordenadas inválidas')
        if min(f.start_line, f.end_line, f.start_col, f.end_col) < 1:
            raise ValueError('Finding com coordenadas não positivas')
        if perfil.no_escopo(f.path):
            encontrados.append(f)
    errors = []
    for raw in dados.get('errors', []):
        # Uniformiza inclusive location.path e mensagens entre worktrees.
        e = json.loads(json.dumps(raw).replace(str(alvo.resolve()) + '/', ''))
        path_raw = e.get('path') or e.get('location', {}).get('path')
        if path_raw:
            p = Path(path_raw)
            if p.is_absolute():
                try: p = p.relative_to(alvo.resolve())
                except ValueError: raise ValueError('Diagnóstico fora do alvo')
            e['path'] = p.as_posix()
            if not perfil.no_escopo(e['path']): continue
        errors.append(e)
    return ScanResultado(encontrados, errors, dados.get('version', ''))


def conferir_versao(semgrep_bin, perfil):
    executable = str(Path(semgrep_bin).resolve()) if '/' in str(semgrep_bin) else str(semgrep_bin)
    v = subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=30)
    lines = v.stdout.strip().splitlines()
    if v.returncode or not lines or lines[-1] != perfil.dados['semgrep_versao']:
        raise ValueError('Versão Semgrep incompatível com o perfil')
    return executable


def scan_perfil(alvo: Path, perfil, saida: Path, semgrep_bin='semgrep') -> ScanResultado:
    perfil.conferir()
    executable = conferir_versao(semgrep_bin, perfil)
    cmd = [executable,'scan','--json','--metrics=off','--no-rewrite-rule-ids','--timeout',str(perfil.dados['timeout_regra_s'])]
    for p in perfil.configs: cmd += ['--config',str(p)]
    for pattern in perfil.dados['escopo']: cmd += ['--exclude',pattern]
    cmd += ['.']
    saida.parent.mkdir(parents=True,exist_ok=True)
    try:
        proc = subprocess.run(cmd,cwd=alvo,capture_output=True,text=True,timeout=perfil.dados['timeout_processo_s'])
    except subprocess.TimeoutExpired:
        return ScanResultado([], [], perfil.dados['semgrep_versao'], 'timeout_processo')
    saida.with_suffix('.stderr.log').write_text(proc.stderr)
    try:
        dados=json.loads(proc.stdout)
    except ValueError:
        return ScanResultado([],[],perfil.dados['semgrep_versao'],'json_scan_invalido')
    saida.write_text(json.dumps(dados,ensure_ascii=False,indent=2)+'\n')
    result = carregar_scan_perfil(saida,alvo,perfil)
    if proc.returncode not in (0,1): result.falha_operacional=f'codigo_{proc.returncode}'
    if any('timeout' in str(e.get('type','')).lower() for e in result.diagnosticos): result.falha_operacional='timeout_regra'
    if result.versao != perfil.dados['semgrep_versao']: result.falha_operacional='versao_scan_divergente'
    return result
