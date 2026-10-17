#!/usr/bin/env python3
"""Inicia o pipeline e consolida suas métricas usando config/execucao.yaml."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys
from uuid import uuid4

RAIZ = Path(__file__).resolve().parent
MODOS = ("real", "preflight", "dry-run")


def carregar_config(arquivo: Path) -> dict:
    import yaml

    config = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    campos = {"modo", "casos", "estrategias", "k", "catalogo", "perfil_sast",
              "baseline_testes", "semgrep_bin", "saida_base"}
    opcionais = {"politica_validacao", "mapa_testes", "cache_validacao", "repeticao_api"}
    if not isinstance(config, dict) or not campos <= set(config) or set(config) - campos - opcionais:
        raise ValueError(f"Campos obrigatórios da configuração: {', '.join(sorted(campos))}")
    if config["modo"] not in MODOS:
        raise ValueError("Modo inválido")
    if type(config["k"]) is not int or config["k"] < 1:
        raise ValueError("k deve ser um inteiro positivo, com worktrees já preparadas")
    for campo in ("casos", "estrategias"):
        valores = config[campo]
        if (not isinstance(valores, list) or not valores
                or any(not isinstance(v, str) or not v.strip() or "," in v for v in valores)
                or len(set(valores)) != len(valores)):
            raise ValueError(f"{campo} deve ser uma lista não vazia, sem duplicatas")
    if set(config["estrategias"]) - {"P1", "P2", "P3", "P4"}:
        raise ValueError("Estratégias permitidas: P1, P2, P3 e P4")
    for campo in ("catalogo", "perfil_sast", "baseline_testes", "semgrep_bin", "saida_base"):
        valor = config[campo]
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"{campo} deve ser um caminho não vazio")
        caminho = Path(valor)
        config[campo] = (RAIZ / caminho).resolve()
        if campo != "saida_base" and not config[campo].is_file():
            raise ValueError(f"Arquivo necessário ausente: {config[campo]}")
    for campo in opcionais - {'mapa_testes'}:
        if campo in config:
            permitidos = {'politica_validacao': ('historica_v1','otimizada_v1','relacionada_v1'),
                          'cache_validacao': ('desligado','leitura','leitura-escrita'),
                          'repeticao_api': ('ampla','seletiva-experimental')}
            if config[campo] not in permitidos[campo]:
                raise ValueError(f'{campo} inválido')
    if config.get('politica_validacao') in ('otimizada_v1','relacionada_v1') and not config.get('mapa_testes'):
        raise ValueError('Política de testes relacionados requer mapa_testes')
    if config.get('mapa_testes'):
        config['mapa_testes'] = (RAIZ / config['mapa_testes']).resolve()
        if not config['mapa_testes'].is_file():
            raise ValueError('Mapa de testes ausente')
    return config


def montar_comandos(config: dict, python: str, execucao: str) -> tuple[list[str], list[str]]:
    saida = config["saida_base"] / execucao
    pipeline = [python, str(RAIZ / "src/pipeline/run_pipeline.py"),
                "--execucao", execucao, "--catalogo", str(config["catalogo"]),
                "--perfil-sast", str(config["perfil_sast"]), "--saida", str(saida),
                "--casos", ",".join(config["casos"]),
                "--estrategias", ",".join(config["estrategias"]), "--k", str(config["k"]),
                "--semgrep-bin", str(config["semgrep_bin"]),
                "--baseline-testes", str(config["baseline_testes"])]
    for campo in ("politica_validacao", "mapa_testes", "cache_validacao", "repeticao_api"):
        if config.get(campo) is not None:
            pipeline.extend(["--" + campo.replace("_", "-"), str(config[campo])])
    if config["modo"] == "preflight":
        pipeline.append("--somente-preflight")
    elif config["modo"] == "dry-run":
        pipeline.append("--dry-run")
    metricas = [python, str(RAIZ / "scripts/reports/consolidate_metrics.py"),
                "--execucao", execucao, "--entrada", str(saida),
                "--catalogo", str(config["catalogo"]),
                "--saida", str(config["saida_base"] / f"{execucao}_METRICAS"),
                "--definicao-f", "criterio"]
    return pipeline, metricas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=RAIZ / "config/execucao.yaml",
                        help="YAML alternativo; caminhos internos são relativos ao repositório")
    parser.add_argument("--modo", choices=MODOS, help="Substitui somente o modo do YAML")
    parser.add_argument("--mostrar-comando", action="store_true",
                        help="Mostra os comandos sem executar nem criar resultados")
    args = parser.parse_args(argv)

    # O comando curto funciona com o Python do sistema, sem ativar a .venv.
    venv = RAIZ / ".venv"
    python = venv / "bin/python"
    if python.is_file() and Path(sys.prefix) != venv:
        argumentos = ["--config", str(args.config.resolve())]
        if args.modo:
            argumentos.extend(["--modo", args.modo])
        if args.mostrar_comando:
            argumentos.append("--mostrar-comando")
        try:
            return subprocess.run([str(python), str(Path(__file__).resolve()),
                                   *argumentos], cwd=RAIZ).returncode
        except KeyboardInterrupt:
            return 130
    try:
        config = carregar_config(args.config)
        if args.modo:
            config["modo"] = args.modo
        execucao = f"AMP_{config['modo'].upper().replace('-', '_')}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
        pipeline, metricas = montar_comandos(config, sys.executable, execucao)
        if args.mostrar_comando:
            print(shlex.join(pipeline))
            print(shlex.join(metricas))
            return 0
        print(f"Modo: {config['modo']} | Casos: {', '.join(config['casos'])} | K={config['k']}", flush=True)
        print(f"Resultados: {config['saida_base'] / execucao}", flush=True)
        if config["modo"] == "real":
            print("Execução real: chamadas à LLM sujeitas aos limites acumulados do .env.", flush=True)
        # Herda o terminal para exibir o progresso do orquestrador original.
        for comando in (pipeline, metricas):
            resultado = subprocess.run(comando, cwd=RAIZ)
            if resultado.returncode:
                print("Etapa interrompida; consulte os artefatos preservados acima.", file=sys.stderr)
                return resultado.returncode if resultado.returncode > 0 else 1
        print(f"Métricas: {config['saida_base'] / (execucao + '_METRICAS')}")
        return 0
    except (ValueError, OSError, ImportError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
