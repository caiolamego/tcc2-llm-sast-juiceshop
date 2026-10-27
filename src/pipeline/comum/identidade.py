"""Identidades por conteúdo, sem caminho absoluto ou dados secretos."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading

_LOCK = threading.Lock()
_DEPENDENCIAS = {}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def inventario(root, excluir=()):
    root = Path(root).resolve()
    result = []
    for pasta, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in excluir)
        for nome in sorted(files + [d for d in dirs if (Path(pasta)/d).is_symlink()]):
            path = Path(pasta) / nome
            rel = path.relative_to(root).as_posix()
            stat = path.lstat()
            if path.is_symlink():
                if not path.resolve().is_relative_to(root):
                    raise ValueError(f'Symlink externo impede identidade confiável: {rel}')
                result.append((rel, 'link', os.readlink(path), stat.st_mtime_ns))
            elif path.is_file():
                result.append((rel, 'file', stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_mode))
            else:
                raise ValueError(f'Arquivo especial impede identidade: {rel}')
    return result


def conteudo(root, entries):
    return [(item[0], item[1], item[2] if item[1] == 'link' else digest(root/item[0]),
             None if item[1]=='link' else item[5] & 0o777) for item in entries]


def dependencias(root):
    entries = inventario(root)
    signature = hash_json(entries)
    with _LOCK:
        old = _DEPENDENCIAS.get(str(root))
        if old and old[0] == signature:
            return old[1]
    value = hash_json(conteudo(root, entries))
    if inventario(root) != entries:
        raise ValueError('Dependências alteradas durante fingerprint')
    with _LOCK:
        _DEPENDENCIAS[str(root)] = (signature, value)
    return value


def versao(cmd):
    return subprocess.check_output(cmd, text=True, timeout=30).strip()


def ambiente(wt):
    wt = Path(wt)
    return {'node': versao(['node', '--version']),
            'npm': versao(['npm', '--version']),
            'typescript': json.loads((wt/'node_modules/typescript/package.json').read_text())['version'],
            'lock_sha256': digest(wt/'package-lock.json'),
            'instalacao_lock_sha256': digest(wt/'node_modules/.package-lock.json'),
            'dependencias_sha256': dependencias(wt/'node_modules'),
            'TZ': 'UTC', 'NODE_ENV': 'test',
            'variaveis_sha256': hash_json({k: os.environ.get(k) for k in ('NODE_OPTIONS', 'NODE_CONFIG_ENV', 'NODE_CONFIG', 'NODE_PATH')}),
            'porta_api': 3100 + (int(wt.name.rsplit('-',1)[-1]) if wt.name.rsplit('-',1)[-1].isdigit() else 0)}


def estado(wt, funcional=False):
    wt = Path(wt).resolve()
    if funcional:
        entries = inventario(wt, excluir=('.git', 'node_modules'))
        # .git é arquivo nas worktrees; nunca pertence à identidade científica.
        entries = [e for e in entries if e[0] != '.git']
        return hash_json(conteudo(wt, entries))
    nomes = subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'], cwd=wt).decode().split('\0')
    result = []
    for nome in sorted(set(n for n in nomes if n)):
        path = wt/nome
        if not path.resolve().is_relative_to(wt):
            raise ValueError('Fonte fora da worktree')
        result.append((nome, os.readlink(path) if path.is_symlink() else digest(path) if path.is_file() else None,
                       path.stat().st_mode & 0o777 if path.exists() else None))
    return hash_json(result)


def baseline_semantico(scan):
    return hash_json({'versao': scan.versao,
                     'findings': sorted([f.to_dict() for f in scan.findings], key=hash_json),
                     'diagnosticos': sorted(scan.diagnosticos, key=hash_json),
                     'falha_operacional': scan.falha_operacional})
