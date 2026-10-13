"""Pool de worktrees isolados para aplicacao e validacao de correcoes (D4, F4.1)."""
from __future__ import annotations

import queue
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Restauracao e operacao local do git: se passar disso, algo travou.
TIMEOUT_GIT_S = 60

# Preservados no 'git clean'. Ja sao ignorados pelo .gitignore do Juice Shop
# (e 'git clean -fd' sem '-x' nao apaga ignorados), mas o '-e' explicito
# protege contra uma correcao que altere o .gitignore.
PRESERVAR = ["node_modules", "frontend/node_modules"]


class PoolWorktrees:
    """Fila de worktrees livres. Nomes sem zero a esquerda: wt-1 .. wt-K."""

    def __init__(self, raiz: Path, k: int = 4, commit_esperado: str | None = None):
        self.raiz = Path(raiz)
        self.commit_esperado = commit_esperado
        self._livres: queue.Queue[Path] = queue.Queue()
        for i in range(1, k + 1):
            wt = self.raiz / f"wt-{i}"
            if not wt.is_dir():
                raise FileNotFoundError(f"Worktree ausente: {wt}. Rode scripts/setup/setup_target.sh")
            if not (wt / "node_modules").is_dir():
                raise FileNotFoundError(f"{wt} sem node_modules. Rode scripts/setup/setup_target.sh")
            self._conferir_commit(wt)
            self._livres.put(wt)

    def _conferir_commit(self, wt: Path) -> None:
        if not self.commit_esperado:
            return
        head = _git(wt, "rev-parse", "HEAD").stdout.strip()
        if head != self.commit_esperado:
            raise RuntimeError(f"{wt} esta em {head}, esperado {self.commit_esperado}")

    @contextmanager
    def alugar(self, timeout: float = 1800) -> Iterator[Path]:
        """Entrega um worktree limpo e o restaura na devolucao, mesmo com erro."""
        wt = self._livres.get(timeout=timeout)
        try:
            self.restaurar(wt)
            yield wt
        finally:
            self.restaurar(wt)
            self._livres.put(wt)

    @staticmethod
    def restaurar(wt: Path) -> None:
        """Volta o worktree ao commit fixado, preservando node_modules."""
        _git(wt, "checkout", "--", ".")
        args = ["clean", "-fd"]
        for p in PRESERVAR:
            args += ["-e", p]
        _git(wt, *args)

    @staticmethod
    def esta_limpo(wt: Path) -> bool:
        """True se nao ha arquivo rastreado alterado nem arquivo novo nao ignorado."""
        return _git(wt, "status", "--porcelain").stdout.strip() == ""


def _git(wt: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=wt, check=True,
        capture_output=True, text=True, timeout=TIMEOUT_GIT_S,
    )
