"""Validacao em camadas com parada antecipada (D5, F4.2).

Implementado: T0 (compilacao), T2 (teste do arquivo alterado), T3 (suite
unitaria de servidor), T4 (testes de API). T5 (Cypress) fica para depois.
Comandos e TZ reaproveitados de scripts/measure_validation_cost.py.

Linha de base (decisao do grupo, 2026-10-07): T2/T3/T4 passam quando o
conjunto de testes que falharam esta contido no conjunto que ja falha no
worktree sem alteracao (outputs/baseline_testes.json, gerado por
scripts/baseline_testes.py). Nenhum teste e pulado por nome.
"""
from __future__ import annotations

import html
import json
import os
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pipeline.caminhos import RAIZ_REPO, rel, relativizar_texto

# Bug de fuso do Juice Shop em toISO8601 (caderno, F2.4): todo subprocesso
# roda com TZ=UTC. Setado aqui e tambem passado explicitamente no env.
os.environ["TZ"] = "UTC"

CMD_T0 = ["npx", "tsc", "--noEmit"]

# T2/T3/T4 chamam o node direto, com os mesmos argumentos dos scripts
# 'test:server' e 'test:api' do package.json, para acrescentar o reporter
# JUnit (lista de testes que falharam, sem depender do texto da tela).
# 'npm run ... -- --test-reporter' nao serve: o npm poe os argumentos depois
# do glob, onde o node os trataria como padrao de arquivo.
SETUP_SERVIDOR = "./test/server/helpers/test-env.mjs"
SETUP_API = "./test/api/helpers/test-env.mjs"
GLOB_T3 = "test/server/**/*.unit.test.ts"
GLOB_T4 = "test/api/**/*.test.ts"
# T4 nao usa 'npm start': os testes de API criam o app em memoria (supertest),
# mas importar server.ts dispara validatePreconditions, que checa se a porta
# (process.env.PORT ou 3000) esta livre e da process.exit(1) se nao estiver.
# Por isso cada worktree recebe PORT propria (PORTA_BASE_T4 + numero do wt).
# Limite conhecido: test/api/chat.test.ts usa a porta fixa 43210 (caderno).
PORTA_BASE_T4 = 3100

PASTA_TESTES_SERVIDOR = "test/server"
SUFIXO_TESTE_UNITARIO = ".unit.test.ts"
TAMANHO_SAIDA = 4000  # caracteres finais guardados de stdout+stderr
ARQ_LINHA_DE_BASE = RAIZ_REPO / "outputs" / "baseline_testes.json"


def cmd_testes(setup: str, padroes: list[str], destino_junit: Path) -> list[str]:
    return ["node", "--import", setup, "--import", "tsx", "--test", "--test-force-exit",
            "--test-reporter=spec", "--test-reporter-destination=stdout",
            "--test-reporter=junit", f"--test-reporter-destination={destino_junit}",
            *padroes]


@dataclass
class ConfigValidacao:
    # Medianas medidas em F2.4: T0~1,5s, T2~0,5s, T3~2s, T4~13-17s. Timeouts
    # bem acima de 10x a mediana, porque 'npx' frio e maquina carregada pesam.
    timeout_t0_s: float = 120
    timeout_t2_s: float = 60
    timeout_t3_s: float = 300
    timeout_t4_s: float = 300
    rodar_t4: bool = True
    arquivo_linha_de_base: Path = ARQ_LINHA_DE_BASE


@dataclass
class ResultadoTier:
    tier: str
    comando: list[str]
    passou: bool
    duracao_s: float
    # falha | timeout | comando_nao_encontrado | falha_sem_relatorio
    # | so_falhas_da_linha_de_base (passou, mas com falhas ja conhecidas)
    motivo: str | None = None
    codigo_saida: int | None = None
    testes_falhos: list[str] = field(default_factory=list)
    testes_falhos_novos: list[str] = field(default_factory=list)
    saida: str = ""


@dataclass
class ResultadoValidacao:
    passou: bool
    tier_falha: str | None
    duracao_s: float
    tiers: list[ResultadoTier] = field(default_factory=list)
    t2_pulado: bool = False
    testes_t2: list[str] = field(default_factory=list)
    testes_falhos_novos: list[str] = field(default_factory=list)
    linha_de_base: str | None = None

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
            r = t.relative_to(wt).as_posix()
            if r not in achados:
                achados.append(r)
    return achados


def porta_t4(wt: Path) -> int:
    """wt-3 -> 3103. Fora do padrao wt-N, usa a porta base."""
    sufixo = wt.name.rsplit("-", 1)[-1]
    return PORTA_BASE_T4 + (int(sufixo) if sufixo.isdigit() else 0)


def testes_falhos_junit(xml: Path, wt: Path) -> list[str] | None:
    """Identificador estavel de cada teste que falhou:
    '<arquivo relativo> :: <suite> > <subsuite> > <teste>'.
    None se o relatorio nao existe ou nao pode ser lido."""
    if not xml.exists() or xml.stat().st_size == 0:
        return None
    try:
        raiz = ET.parse(xml).getroot()
    except ET.ParseError:
        return None
    falhos: list[str] = []

    def visitar(no: ET.Element, suites: list[str]) -> None:
        for filho in no:
            if filho.tag == "testsuite":
                visitar(filho, suites + [filho.get("name", "")])
            elif filho.tag == "testcase" and filho.find("failure") is not None:
                arq = filho.get("file", "")
                try:
                    arq = Path(arq).resolve().relative_to(wt.resolve()).as_posix()
                except ValueError:
                    pass
                # O reporter do node escapa o nome duas vezes (&amp;quot;).
                nomes = [html.unescape(n) for n in suites + [filho.get("name", "")]]
                ident = f"{arq} :: {' > '.join(nomes)}"
                if ident not in falhos:
                    falhos.append(ident)

    visitar(raiz, [])
    return sorted(falhos)


def _rodar(tier: str, cmd: list[str], wt: Path, timeout_s: float,
           env_extra: dict[str, str] | None = None) -> tuple[ResultadoTier, int | None]:
    """Roda em grupo de processos proprio para matar netos (npx/npm -> node) no
    timeout. Devolve o resultado e o codigo de saida (None em timeout)."""
    env = {**os.environ, "TZ": "UTC", **(env_extra or {})}
    cmd_registro = [relativizar_texto(c) for c in cmd]
    inicio = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd, cwd=wt, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except FileNotFoundError as e:
        return ResultadoTier(tier, cmd_registro, False, 0.0, "comando_nao_encontrado",
                             saida=str(e)), None
    try:
        saida, _ = proc.communicate(timeout=timeout_s)
        duracao = time.monotonic() - inicio
        passou = proc.returncode == 0
        saida = relativizar_texto((saida or "")[-TAMANHO_SAIDA:], wt)
        return ResultadoTier(tier, cmd_registro, passou, round(duracao, 2),
                             None if passou else "falha", proc.returncode,
                             saida=relativizar_texto(saida)), proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        saida, _ = proc.communicate()
        duracao = time.monotonic() - inicio
        saida = relativizar_texto(f"TIMEOUT apos {timeout_s}s\n" + (saida or "")[-TAMANHO_SAIDA:], wt)
        return ResultadoTier(tier, cmd_registro, False, round(duracao, 2), "timeout",
                             saida=relativizar_texto(saida)), None


def rodar_suite(tier: str, wt: Path, timeout_s: float,
                linha_de_base: set[str] | None = None) -> ResultadoTier:
    """Roda T2/T3/T4 com reporter JUnit. Sem linha_de_base, so coleta os
    testes falhos (uso de scripts/baseline_testes.py)."""
    wt = Path(wt).resolve()
    with tempfile.TemporaryDirectory(prefix=f"junit_{tier}_") as tmp:
        xml = Path(tmp) / "resultado.xml"
        if tier == "T4":
            cmd = cmd_testes(SETUP_API, [GLOB_T4], xml)
            env_extra = {"PORT": str(porta_t4(wt))}
        elif tier == "T3":
            cmd, env_extra = cmd_testes(SETUP_SERVIDOR, [GLOB_T3], xml), {}
        else:
            raise ValueError("use rodar_t2 para o T2")
        return _avaliar(tier, cmd, wt, timeout_s, env_extra, xml, linha_de_base)


def rodar_t2(wt: Path, testes: list[str], timeout_s: float,
             linha_de_base: set[str] | None) -> ResultadoTier:
    wt = Path(wt).resolve()
    with tempfile.TemporaryDirectory(prefix="junit_T2_") as tmp:
        xml = Path(tmp) / "resultado.xml"
        return _avaliar("T2", cmd_testes(SETUP_SERVIDOR, testes, xml), wt, timeout_s,
                        {}, xml, linha_de_base)


def _avaliar(tier: str, cmd: list[str], wt: Path, timeout_s: float, env_extra: dict,
             xml: Path, linha_de_base: set[str] | None) -> ResultadoTier:
    r, codigo = _rodar(tier, cmd, wt, timeout_s, env_extra)
    # O caminho do XML temporario nao interessa no registro.
    r.comando = [c for c in r.comando if not c.startswith("--test-reporter-destination=/")]
    if r.motivo in ("timeout", "comando_nao_encontrado"):
        return r
    falhos = testes_falhos_junit(xml, wt)
    if falhos is None:
        if codigo != 0:
            r.passou, r.motivo = False, "falha_sem_relatorio"
        return r
    r.testes_falhos = falhos
    if linha_de_base is None:
        return r
    r.testes_falhos_novos = sorted(set(falhos) - linha_de_base)
    if codigo != 0 and not falhos:
        # Saiu com erro sem nenhum teste falho no relatorio (ex.: erro ao
        # carregar um arquivo de teste): nao da para afirmar que preservou.
        r.passou, r.motivo = False, "falha_sem_relatorio"
    elif r.testes_falhos_novos:
        r.passou, r.motivo = False, "falha"
    else:
        r.passou = True
        r.motivo = "so_falhas_da_linha_de_base" if falhos else None
    return r


def carregar_linha_de_base(arquivo: Path, wt: Path) -> dict[str, set[str]]:
    if not arquivo.exists():
        raise FileNotFoundError(f"Linha de base ausente: {rel(arquivo)}. "
                                "Rode scripts/baseline_testes.py")
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True,
                          text=True, timeout=30).stdout.strip()
    if dados.get("commit_alvo") != head:
        raise RuntimeError(f"Linha de base gerada em {dados.get('commit_alvo')}, "
                           f"mas {wt.name} esta em {head}. Regere a linha de base.")
    return {tier: set(info["testes_falhos"]) for tier, info in dados["tiers"].items()}


def validar(wt: Path, arquivos_alterados: list[str],
            cfg: ConfigValidacao | None = None) -> ResultadoValidacao:
    """Escada T0 -> T2 -> T3 -> T4 com parada no primeiro tier que falhar.

    Retorna passou, tier_falha (None se passou), duracao_s total, a saida de
    cada camada executada e testes_falhos_novos (falhas alem da linha de base).
    """
    cfg = cfg or ConfigValidacao()
    wt = Path(wt).resolve()
    base = carregar_linha_de_base(cfg.arquivo_linha_de_base, wt)
    inicio = time.monotonic()
    res = ResultadoValidacao(passou=False, tier_falha=None, duracao_s=0.0,
                             linha_de_base=rel(cfg.arquivo_linha_de_base))

    testes_t2 = testes_relacionados(wt, arquivos_alterados)
    res.testes_t2 = testes_t2
    res.t2_pulado = not testes_t2

    passos = [("T0", lambda: _rodar("T0", CMD_T0, wt, cfg.timeout_t0_s)[0])]
    if testes_t2:
        # Os testes do T2 sao um subconjunto da suite do T3: mesma linha de base.
        passos.append(("T2", lambda: rodar_t2(wt, testes_t2, cfg.timeout_t2_s,
                                              base.get("T3", set()))))
    passos.append(("T3", lambda: rodar_suite("T3", wt, cfg.timeout_t3_s, base.get("T3", set()))))
    if cfg.rodar_t4:
        passos.append(("T4", lambda: rodar_suite("T4", wt, cfg.timeout_t4_s, base.get("T4", set()))))

    for tier, rodar in passos:
        r = rodar()
        res.tiers.append(r)
        for t in r.testes_falhos_novos:
            if t not in res.testes_falhos_novos:
                res.testes_falhos_novos.append(t)
        if not r.passou:
            res.tier_falha = tier
            break
    else:
        res.passou = True

    res.duracao_s = round(time.monotonic() - inicio, 2)
    return res
