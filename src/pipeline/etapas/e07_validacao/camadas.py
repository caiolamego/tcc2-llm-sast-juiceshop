"""Validacao em camadas com parada antecipada (D5, F4.2).

Implementado: T0 (compilacao), T2 (teste do arquivo alterado), T3 (suite
unitaria de servidor), T4 (testes de API). T5 (Cypress) fica para depois.
Comandos e TZ reaproveitados de scripts/measure_validation_cost.py.

Linha de base (protocolo, Secao 7.1): T2/T3/T4 passam quando o conjunto de
testes que falharam esta contido no conjunto que ja falha no worktree sem
alteracao (outputs/baseline_testes.json, gerado por scripts/experimento/gerar_linha_de_base_historica.py).
Nenhum teste e pulado por nome. Com falhas novas, a camada roda de novo e so
conta a intersecao das duas rodadas (Secao 7.2).
"""
from __future__ import annotations

import html
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pipeline.comum.caminhos import RAIZ_REPO, rel, relativizar_texto
from pipeline.etapas.e07_validacao.conjunto_d import classificar

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
    # T4 serializado entre worktrees: chat.test.ts usa a porta fixa 43210
    # (protocolo, Secao 7). A reexecucao da Secao 7.2 roda dentro do lock.
    lock_t4: threading.Lock | None = None
    politica: str = 'historica_v1'
    mapa: Path | None = None
    repeticao_api: str = 'ampla'
    cobertura: Path | None = None


@dataclass
class ResultadoTier:
    tier: str
    comando: list[str]
    passou: bool
    duracao_s: float
    # falha | timeout | comando_nao_encontrado | falha_sem_relatorio
    # | so_falhas_da_linha_de_base (passou, mas com falhas ja conhecidas)
    # | so_falhas_intermitentes (passou: falhas novas nao se repetiram)
    motivo: str | None = None
    codigo_saida: int | None = None
    testes_falhos: list[str] = field(default_factory=list)
    # Apos a reexecucao, so a intersecao das duas rodadas (Secao 7.2).
    testes_falhos_novos: list[str] = field(default_factory=list)
    reexecucoes: int = 0
    timeout_na_primeira_rodada: bool = False
    testes_falhos_intermitentes: list[str] = field(default_factory=list)
    testes_falhos_reexecucao: list[str] = field(default_factory=list)
    # Separacao F/D dos testes falhos novos, nas duas definicoes (Secao 13).
    # 'passou' acima e a camada sem separacao (qualquer falha nova reprova).
    testes_falhos_d_marcador: list[str] = field(default_factory=list)
    testes_falhos_d_criterio: list[str] = field(default_factory=list)
    testes_falhos_f_marcador: list[str] = field(default_factory=list)
    testes_falhos_f_criterio: list[str] = field(default_factory=list)
    saida: str = ""
    saida_reexecucao: str = ""
    espera_api_s: float = 0.0
    repeticao_seletiva: dict | None = None


@dataclass
class ResultadoValidacao:
    # passou/tier_falha seguem a definicao d_criterio (Secao 7.1); as tres
    # versoes ficam em F_* e tier_falha_*.
    passou: bool | None
    tier_falha: str | None
    duracao_s: float
    F_sem_separacao: bool | None = False
    F_marcador: bool | None = False
    F_criterio: bool | None = False
    tier_falha_sem_separacao: str | None = None
    tier_falha_marcador: str | None = None
    tier_falha_criterio: str | None = None
    testes_falhos_d_marcador: list[str] = field(default_factory=list)
    testes_falhos_d_criterio: list[str] = field(default_factory=list)
    testes_falhos_f_marcador: list[str] = field(default_factory=list)
    testes_falhos_f_criterio: list[str] = field(default_factory=list)
    tiers: list[ResultadoTier] = field(default_factory=list)
    t2_pulado: bool = False
    testes_t2: list[str] = field(default_factory=list)
    testes_falhos_novos: list[str] = field(default_factory=list)
    reexecucoes: int = 0
    testes_falhos_intermitentes: list[str] = field(default_factory=list)
    linha_de_base: str | None = None
    selecao: dict | None = None
    etapas: list[dict] = field(default_factory=list)
    duracao_selecao_s: float = 0.0
    escopo: str = 'amplo'
    cobertura_insuficiente: bool = False
    cobertura_detalhada: dict | None = None

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
    from pipeline.etapas.e05_geracao_llm.provedor import ambiente_alvo
    env = ambiente_alvo({"TZ": "UTC", **(env_extra or {})})
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
    except BaseException:
        try:os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:pass
        proc.communicate()
        raise


def rodar_suite(tier: str, wt: Path, timeout_s: float,
                linha_de_base: set[str] | None = None, repeticao='ampla') -> ResultadoTier:
    """Roda T2/T3/T4 com reporter JUnit. Sem linha_de_base, so coleta os
    testes falhos (uso de scripts/experimento/gerar_linha_de_base_historica.py)."""
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
        return _avaliar(tier, cmd, wt, timeout_s, env_extra, xml, linha_de_base,
                        seletiva=(tier == 'T4' and repeticao == 'seletiva-experimental'))


def rodar_t2(wt: Path, testes: list[str], timeout_s: float,
             linha_de_base: set[str] | None) -> ResultadoTier:
    wt = Path(wt).resolve()
    with tempfile.TemporaryDirectory(prefix="junit_T2_") as tmp:
        xml = Path(tmp) / "resultado.xml"
        return _avaliar("T2", cmd_testes(SETUP_SERVIDOR, testes, xml), wt, timeout_s,
                        {}, xml, linha_de_base)


def _uma_rodada(tier: str, cmd: list[str], wt: Path, timeout_s: float, env_extra: dict,
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


def _avaliar(tier: str, cmd: list[str], wt: Path, timeout_s: float, env_extra: dict,
             xml: Path, linha_de_base: set[str] | None, seletiva=False) -> ResultadoTier:
    """Uma rodada; se houver testes falhos novos, reexecuta uma vez e so conta
    a intersecao das falhas novas. Timeout tambem dispara uma reexecucao, e
    vale o resultado dela (protocolo, Secao 7.2)."""
    r = _uma_rodada(tier, cmd, wt, timeout_s, env_extra, xml, linha_de_base)
    if linha_de_base is not None and r.motivo == "timeout":
        r2 = _uma_rodada(tier, cmd, wt, timeout_s, env_extra, xml, linha_de_base)
        r2.reexecucoes = 1
        r2.duracao_s = round(r.duracao_s + r2.duracao_s, 2)
        r2.saida_reexecucao, r2.saida = r2.saida, r.saida
        r2.timeout_na_primeira_rodada = True
        # Sem relatorio da 1a rodada nao ha intersecao: vale a 2a, sozinha.
        return r2
    if linha_de_base is None or r.motivo != "falha":
        return r

    r2 = None
    if seletiva:
        from pipeline.etapas.e07_validacao.repeticao import repetir_seletivo
        r2, info = repetir_seletivo(r, wt, timeout_s, env_extra, linha_de_base)
        r.repeticao_seletiva = info
    if r2 is None:
        r2 = _uma_rodada(tier, cmd, wt, timeout_s, env_extra, xml, linha_de_base)
    descartada = (r.repeticao_seletiva or {}).get('duracao_descartada_s', 0)
    r.reexecucoes = 1 + int(bool(descartada))
    r.duracao_s = round(r.duracao_s + r2.duracao_s + descartada, 2)
    r.testes_falhos_reexecucao = r2.testes_falhos
    r.saida_reexecucao = r2.saida
    if r2.motivo in ("timeout", "comando_nao_encontrado", "falha_sem_relatorio"):
        # Segunda rodada sem relatorio confiavel: mantem a primeira (conservador).
        r.motivo = f"falha (reexecucao: {r2.motivo})"
        return r
    n1, n2 = set(r.testes_falhos_novos), set(r2.testes_falhos_novos)
    r.testes_falhos_novos = sorted(n1 & n2)
    r.testes_falhos_intermitentes = sorted(n1 ^ n2)
    if r.testes_falhos_novos:
        r.passou, r.motivo = False, "falha"
    else:
        r.passou, r.motivo = True, "so_falhas_intermitentes"
    return r


def carregar_linha_de_base(arquivo: Path, wt: Path) -> dict[str, set[str]]:
    if not arquivo.exists():
        raise FileNotFoundError(f"Linha de base ausente: {rel(arquivo)}. "
                                "Rode scripts/experimento/gerar_linha_de_base_historica.py")
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True,
                          text=True, timeout=30).stdout.strip()
    if dados.get("commit_alvo") != head:
        raise RuntimeError(f"Linha de base gerada em {dados.get('commit_alvo')}, "
                           f"mas {wt.name} esta em {head}. Regere a linha de base.")
    return {tier: set(info["testes_falhos"]) for tier, info in dados["tiers"].items()}


def _t0(wt: Path, timeout_s: float) -> ResultadoTier:
    """Compilacao; timeout dispara uma reexecucao, como nas demais camadas (7.2)."""
    r = _rodar("T0", CMD_T0, wt, timeout_s)[0]
    if r.motivo != "timeout":
        return r
    r2 = _rodar("T0", CMD_T0, wt, timeout_s)[0]
    r2.reexecucoes, r2.timeout_na_primeira_rodada = 1, True
    r2.duracao_s = round(r.duracao_s + r2.duracao_s, 2)
    return r2


def _t4_serializado(wt: Path, cfg: ConfigValidacao, base: set[str]) -> ResultadoTier:
    if cfg.lock_t4 is None:
        return rodar_suite("T4", wt, cfg.timeout_t4_s, base, cfg.repeticao_api)
    inicio = time.monotonic()
    with cfg.lock_t4:
        espera = time.monotonic()-inicio
        resultado = rodar_suite("T4", wt, cfg.timeout_t4_s, base, cfg.repeticao_api)
        resultado.espera_api_s = espera
        return resultado


def _api_relacionada(wt, cfg, testes, base):
    from contextlib import nullcontext
    inicio = time.monotonic()
    with (cfg.lock_t4 if cfg.lock_t4 is not None else nullcontext()):
        espera = time.monotonic()-inicio
        with tempfile.TemporaryDirectory(prefix='junit_API_REL_') as tmp:
            xml = Path(tmp)/'resultado.xml'
            resultado = _avaliar('T2_API', cmd_testes(SETUP_API, testes, xml), wt,
                                 cfg.timeout_t4_s, {'PORT':str(porta_t4(wt))}, xml, base)
            resultado.espera_api_s = espera
            return resultado


def validar(wt: Path, arquivos_alterados: list[str],
            cfg: ConfigValidacao | None = None, entre_etapas=None) -> ResultadoValidacao:
    """Escada T0 -> T2 -> T3 -> T4.

    Cada camada classifica os testes falhos novos em D/F nas duas definicoes
    (d_marcador, d_criterio). A escada so para quando a camada falha por algo
    que nao e D nem na definicao mais ampla (d_criterio), ou por falha sem
    testes (compilacao, timeout, erro sem relatorio). Assim, numa unica
    validacao saem F sem separacao, F_marcador e F_criterio, encaixados:
    F_sem_separacao <= F_marcador <= F_criterio.
    """
    cfg = cfg or ConfigValidacao()
    wt = Path(wt).resolve()
    if cfg.politica == 'relacionada_v2':
        from pipeline.etapas.e07_validacao.execucao_cobertura import validar as validar_cobertura
        return validar_cobertura(wt,arquivos_alterados,cfg,entre_etapas)
    base = carregar_linha_de_base(cfg.arquivo_linha_de_base, wt)
    inicio = time.monotonic()
    res = ResultadoValidacao(passou=False, tier_falha=None, duracao_s=0.0,
                             linha_de_base=rel(cfg.arquivo_linha_de_base))

    testes_t2 = testes_relacionados(wt, arquivos_alterados)
    res.testes_t2 = testes_t2
    res.t2_pulado = not testes_t2

    passos = [("T0", lambda: _t0(wt, cfg.timeout_t0_s))]
    if testes_t2:
        # Os testes do T2 sao um subconjunto da suite do T3: mesma linha de base.
        passos.append(("T2", lambda: rodar_t2(wt, testes_t2, cfg.timeout_t2_s,
                                              base.get("T3", set()))))
    passos.append(("T3", lambda: rodar_suite("T3", wt, cfg.timeout_t3_s, base.get("T3", set()))))
    if cfg.rodar_t4:
        passos.append(("T4", lambda: _t4_serializado(wt, cfg, base.get("T4", set()))))

    limite_triagem = 0
    relacionada = cfg.politica == 'relacionada_v1'
    if cfg.politica in ('otimizada_v1', 'relacionada_v1'):
        from pipeline.etapas.e07_validacao.selecao import selecionar
        if not cfg.mapa:
            raise ValueError('Política de testes relacionados requer mapa de testes')
        selecao_inicio = time.monotonic()
        selecao = selecionar(cfg.mapa, wt, arquivos_alterados)
        res.duracao_selecao_s = time.monotonic()-selecao_inicio
        res.selecao = selecao.to_dict()
        if relacionada:
            res.escopo = 'relacionado'
            res.cobertura_insuficiente = selecao.fallback or bool(selecao.api and not cfg.rodar_t4)
        res.testes_t2, res.t2_pulado = selecao.unitarios, not selecao.unitarios
        passos = [('T0', lambda: _t0(wt, cfg.timeout_t0_s))]
        if relacionada or not selecao.fallback:
            if selecao.unitarios:
                passos.append(('T2', lambda: rodar_t2(wt, selecao.unitarios, cfg.timeout_t2_s, base.get('T3',set()))))
            if selecao.api and cfg.rodar_t4:
                passos.append(('T2_API', lambda: _api_relacionada(wt,cfg,selecao.api,base.get('T4',set()))))
        limite_triagem = len(passos)
        if not relacionada:
            passos.append(('T3', lambda: rodar_suite('T3',wt,cfg.timeout_t3_s,base.get('T3',set()))))
            if cfg.rodar_t4:
                passos.append(('T4', lambda: _t4_serializado(wt,cfg,base.get('T4',set()))))

    falha = {"sem_separacao": None, "marcador": None, "criterio": None}
    concluiu = True
    callback_executado = False
    duracao_callback = 0.0
    for indice, (tier, rodar) in enumerate(passos):
        if entre_etapas and indice == limite_triagem:
            inicio_callback = time.monotonic()
            entre_etapas()
            duracao_callback += time.monotonic()-inicio_callback
            callback_executado = True
        r = rodar()
        c = classificar(r.testes_falhos_novos)
        r.testes_falhos_d_marcador, r.testes_falhos_d_criterio = c["d_marcador"], c["d_criterio"]
        r.testes_falhos_f_marcador, r.testes_falhos_f_criterio = c["f_marcador"], c["f_criterio"]
        res.tiers.append(r)
        res.etapas.append({'tier':tier, 'status':'executada', 'duracao_s':r.duracao_s})
        res.reexecucoes += r.reexecucoes
        for origem, destino in (
                (r.testes_falhos_novos, res.testes_falhos_novos),
                (r.testes_falhos_intermitentes, res.testes_falhos_intermitentes),
                (r.testes_falhos_d_marcador, res.testes_falhos_d_marcador),
                (r.testes_falhos_d_criterio, res.testes_falhos_d_criterio),
                (r.testes_falhos_f_marcador, res.testes_falhos_f_marcador),
                (r.testes_falhos_f_criterio, res.testes_falhos_f_criterio)):
            for t in origem:
                if t not in destino:
                    destino.append(t)
        # Falha sem testes nomeados (compilacao, timeout, sem relatorio) reprova
        # em todas as definicoes; com testes, depende de quais sao D.
        so_testes = not r.passou and bool(r.testes_falhos_novos)
        ok = {"sem_separacao": r.passou,
              "marcador": r.passou or (so_testes and not r.testes_falhos_f_marcador),
              "criterio": r.passou or (so_testes and not r.testes_falhos_f_criterio)}
        for k, v in ok.items():
            if not v and falha[k] is None:
                falha[k] = tier
        if not ok["criterio"]:
            concluiu = False
            break

    if entre_etapas and not callback_executado:
        inicio_callback = time.monotonic()
        entre_etapas()  # SAST continua observável mesmo com F reprovado na triagem.
        duracao_callback += time.monotonic()-inicio_callback
    realizados = {r.tier for r in res.tiers}
    for tier, _ in passos:
        if tier not in realizados:
            res.etapas.append({'tier':tier, 'status':'dispensada_por_reprovacao',
                               'motivo':'F_criterio reprovado em etapa anterior', 'duracao_s':None})

    res.tier_falha_sem_separacao = falha["sem_separacao"]
    res.tier_falha_marcador = falha["marcador"]
    res.tier_falha_criterio = falha["criterio"]
    res.F_sem_separacao = concluiu and falha["sem_separacao"] is None
    res.F_marcador = concluiu and falha["marcador"] is None
    res.F_criterio = concluiu and falha["criterio"] is None
    if relacionada:
        for tier in ('T3', 'T4'):
            res.etapas.append({'tier': tier, 'status': 'nao_aplicavel',
                               'motivo': 'relacionada_v1: somente testes mapeados da funcionalidade',
                               'duracao_s': None})
        if res.cobertura_insuficiente:
            for definicao in ('sem_separacao', 'marcador', 'criterio'):
                if getattr(res, 'F_' + definicao):
                    setattr(res, 'F_' + definicao, None)
                    setattr(res, 'tier_falha_' + definicao, 'cobertura_insuficiente')
    res.passou, res.tier_falha = res.F_criterio, res.tier_falha_criterio

    res.duracao_s = round(time.monotonic() - inicio - duracao_callback, 2)
    return res
