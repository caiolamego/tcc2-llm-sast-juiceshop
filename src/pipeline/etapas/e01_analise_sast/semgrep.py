"""Execucao e normalizacao dos resultados do Semgrep."""
from __future__ import annotations

from pipeline.etapas.e05_geracao_llm.provedor import ambiente_alvo

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


# Sem login, o Semgrep devolve este texto no lugar de extra.fingerprint e de
# extra.lines (caderno, 2026-10-07). Tratado como campo ausente.
SENTINELA_SEM_LOGIN = "requires login"


def _sem_sentinela(valor: str) -> str:
    return "" if valor.strip() == SENTINELA_SEM_LOGIN else valor


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
    v = subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=30,env=ambiente_alvo())
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
        proc = subprocess.run(cmd,cwd=alvo,capture_output=True,text=True,timeout=perfil.dados['timeout_processo_s'],env=ambiente_alvo())
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
