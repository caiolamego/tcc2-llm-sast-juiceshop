#!/usr/bin/env python3
"""Prepara cópias verificadas e atômicas; reparos preservam conteúdo anterior."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import uuid4

ITEMS = ('node_modules', 'frontend/node_modules', 'build', 'frontend/dist',
         'package-lock.json', 'frontend/package-lock.json')


def fingerprint(path: Path) -> str:
    """Conteúdo, nomes, permissões e links; sem datas ou caminhos absolutos."""
    path = Path(path)
    if path.is_symlink(): raise ValueError('Item raiz não pode ser symlink: ' + str(path))
    rows = []
    def visit(p, name):
        mode = p.lstat().st_mode & 0o777
        if p.is_symlink():
            if not p.resolve().is_relative_to(path.resolve()):
                raise ValueError(f'Link externo: {name}')
            rows.append((name, 'link', mode, os.readlink(p)))
        elif p.is_dir():
            rows.append((name, 'dir', mode))
            for child in sorted(p.iterdir()): visit(child, name + '/' + child.name)
        elif p.is_file():
            h = hashlib.sha256()
            with p.open('rb') as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b''): h.update(data)
            rows.append((name, 'file', mode, h.hexdigest()))
        else: raise ValueError(f'Arquivo especial/ausente: {name}')
    visit(path, '.')
    return hashlib.sha256(json.dumps(rows, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def copy_verified(source, dest, expected, workspace, repair=False):
    source, dest, workspace = Path(source), Path(dest), Path(workspace)
    if dest.exists() or dest.is_symlink():
        if fingerprint(dest) == expected: return 'conferido'
        if not repair:
            raise ValueError(f'Cópia divergente/incompleta: {dest}. Use make docker-repair; nada foi substituído.')
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.preparacao-', dir=dest.parent))
    payload = temporary/'conteudo'
    try:
        if source.is_dir(): shutil.copytree(source, payload, symlinks=True)
        else: shutil.copy2(source, payload)
        if fingerprint(payload) != expected or fingerprint(source) != expected:
            raise ValueError('Conteúdo mudou durante a cópia: ' + str(source))
        if dest.exists() or dest.is_symlink():
            backup = workspace/'.recuperacao'/uuid4().hex
            backup.mkdir(parents=True)
            target = backup/dest.name
            # O caminho original fica registrado ao lado da cópia preservada.
            (backup/'origem.json').write_text(json.dumps({'origem':str(dest.relative_to(workspace))})+'\n')
            dest.rename(target)
            print(f'Preservado em {target}', flush=True)
        payload.rename(dest)
        return 'copiado'
    finally:
        shutil.rmtree(temporary)


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def prepare(reference, workspace, k, repair=False):
    reference, workspace = Path(reference).resolve(), Path(workspace).resolve()
    if k < 1: raise ValueError('K deve ser positivo')
    workspace.mkdir(parents=True, exist_ok=True)
    # Mesmo lock do pipeline: impede preparar/reparar worktrees em uso.
    cache = Path('/repo/.cache')
    if workspace.parent == Path('/repo'): cache.mkdir(exist_ok=True)
    else: cache = workspace
    with (cache/'workspace_execucao.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ValueError('Workspace em uso por outra execução/preparação') from exc
        commit = git(reference, 'rev-parse', 'HEAD')
        if git(reference, 'status', '--porcelain', '--untracked-files=all'):
            raise ValueError('Referência da imagem alterada')
        print('Conferindo referência da imagem...', flush=True)
        hashes = {name:fingerprint(reference/name) for name in ITEMS}
        bare = workspace/'juice-shop.git'
        if not bare.exists(): subprocess.run(['git','clone','--quiet','--mirror',str(reference),str(bare)],check=True)
        for name in ['catalogo-alvo'] + [f'wt-{i}' for i in range(1,k+1)]:
            wt = workspace/name
            if not wt.exists():
                subprocess.run(['git',f'--git-dir={bare}','worktree','add','--quiet','--detach',str(wt),commit],check=True)
            if git(wt,'rev-parse','HEAD') != commit or git(wt,'status','--porcelain','--untracked-files=all'):
                raise ValueError(f'{name} alterado ou em outro commit; nenhum arquivo será restaurado')
            if name == 'catalogo-alvo': continue
            for item in ITEMS:
                state = copy_verified(reference/item, wt/item, hashes[item], workspace, repair)
                print(f'{name}: {item}: {state}', flush=True)
        print(f'Pronto: {k} worktrees verificadas no commit {commit}', flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('k',type=int,nargs='?',default=4)
    parser.add_argument('--reparar-incompletos',action='store_true')
    args=parser.parse_args()
    try:
        if not Path('/opt/ambiente.json').is_file(): raise ValueError('Execute dentro do container')
        prepare('/opt/juice-shop','/repo/workspace',args.k,args.reparar_incompletos)
        return 0
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        print('ERRO:',exc);return 1

if __name__=='__main__':raise SystemExit(main())
