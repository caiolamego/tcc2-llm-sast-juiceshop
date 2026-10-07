"""Validacao em camadas com parada antecipada (D5, F4.2).

Implementado: T0 (compilacao), T2 (teste do arquivo alterado), T3 (suite
unitaria de servidor). T4 (API) e T5 (Cypress) ficam para depois.
Comandos e TZ reaproveitados de scripts/measure_validation_cost.py.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Bug de fuso do Juice Shop em toISO8601 (caderno, F2.4): todo subprocesso
# roda com TZ=UTC. Setado aqui e tambem passado explicitamente no env.
os.environ["TZ"] = "UTC"

CMD_T0 = ["npx", "tsc", "--noEmit"]
# Mesmo comando de 'npm run test:server', mas com arquivo(s) especifico(s).
CMD_T2_BASE = ["node", "--import", "./test/server/helpers/test-env.mjs", "--import", "tsx",
               "--test", "--test-force-exit"]
CMD_T3 = ["npm", "run", "test:server"]

PASTA_TESTES_SERVIDOR = "test/server"
SUFIXO_TESTE_UNITARIO = ".unit.test.ts"
TAMANHO_SAIDA = 4000  # caracteres finais guardados de stdout+stderr


@dataclass
class ConfigValidacao:
    # Medianas medidas em F2.4: T0~1,5s, T2~0,5s, T3~2s. Timeouts bem acima
    # de 10x a mediana, porque 'npx' frio e maquina carregada pesam.
    timeout_t0_s: float = 120
    timeout_t2_s: float = 60
    timeout_t3_s: float = 300


@dataclass
class ResultadoTier:
    tier: str
    comando: list[str]
    passou: bool
    duracao_s: float
    motivo: str | None = None  # "falha", "timeout", "comando_nao_encontrado"
    saida: str = ""


@dataclass
class ResultadoValidacao:
    passou: bool
    tier_falha: str | None
    duracao_s: float
    tiers: list[ResultadoTier] = field(default_factory=list)
    t2_pulado: bool = False
    testes_t2: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def testes_relacionados(wt: Path, arquivos_alterados: list[str]) -> list[str]:
    """Convencao de nome: routes/keyServer.ts -> test/server/keyServer.unit.test.ts.

    Busca recursiva em test/server pelo mesmo nome-base. Sem correspondencia,
    devolve lista vazia e o T2 e pulado.
    """
    pasta = wt / PASTA_TESTES_SERVIDOR
    achados: list[str] = []
    for arq in arquivos_alterados:
        nome = Path(arq).stem + SUFIXO_TESTE_UNITARIO
        for t in sorted(pasta.rglob(nome)):
            rel = t.relative_to(wt).as_posix()
            if rel not in achados:
                achados.append(rel)
    return achados


def _rodar(tier: str, cmd: list[str], wt: Path, timeout_s: float) -> ResultadoTier:
    """Roda em grupo de processos proprio para matar netos (npx/npm -> node) no timeout."""
    env = {**os.environ, "TZ": "UTC"}
    inicio = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd, cwd=wt, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except FileNotFoundError as e:
        return ResultadoTier(tier, cmd, False, 0.0, "comando_nao_encontrado", str(e))
    try:
        saida, _ = proc.communicate(timeout=timeout_s)
        duracao = time.monotonic() - inicio
        passou = proc.returncode == 0
        return ResultadoTier(tier, cmd, passou, round(duracao, 2),
                             None if passou else "falha", (saida or "")[-TAMANHO_SAIDA:])
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        saida, _ = proc.communicate()
        duracao = time.monotonic() - inicio
        return ResultadoTier(tier, cmd, False, round(duracao, 2), "timeout",
                             f"TIMEOUT apos {timeout_s}s\n" + (saida or "")[-TAMANHO_SAIDA:])


def validar(wt: Path, arquivos_alterados: list[str],
            cfg: ConfigValidacao | None = None) -> ResultadoValidacao:
    """Escada T0 -> T2 -> T3 com parada no primeiro tier que falhar.

    Retorna passou, tier_falha (None se passou), duracao_s total e a saida de
    cada camada executada.
    """
    cfg = cfg or ConfigValidacao()
    wt = Path(wt).resolve()
    inicio = time.monotonic()
    res = ResultadoValidacao(passou=False, tier_falha=None, duracao_s=0.0)

    testes_t2 = testes_relacionados(wt, arquivos_alterados)
    res.testes_t2 = testes_t2
    res.t2_pulado = not testes_t2

    escada: list[tuple[str, list[str], float]] = [("T0", CMD_T0, cfg.timeout_t0_s)]
    if testes_t2:
        escada.append(("T2", CMD_T2_BASE + testes_t2, cfg.timeout_t2_s))
    escada.append(("T3", CMD_T3, cfg.timeout_t3_s))

    for tier, cmd, timeout_s in escada:
        r = _rodar(tier, cmd, wt, timeout_s)
        res.tiers.append(r)
        if not r.passou:
            res.tier_falha = tier
            break
    else:
        res.passou = True

    res.duracao_s = round(time.monotonic() - inicio, 2)
    return res
