#!/usr/bin/env python3
"""Inicia o pipeline e consolida suas métricas usando config/execucao.yaml."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys
from uuid import uuid4

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
from pipeline.etapas.e05_geracao_llm.modelos import MODELOS_OPENAI, validar_modelo

MODOS = ("real", "preflight", "dry-run")


def tem_dados_consolidaveis(saida, modo, execucao):
    saida = Path(saida)
    if not (saida/'contrato_execucao.json').is_file():
        return False
    if modo == 'preflight':
        return (saida/'preflight.json').is_file()
    return (saida/'resultados_consolidados/execucoes.jsonl').is_file() or (
        (saida/f'resultados_consolidados/{execucao}_sessoes.json').is_file() and
        (saida/'llm_operacional.jsonl').is_file())


def registrar_finalizacao(saida, execucao, codigo_pipeline, codigo_metricas):
    saida = Path(saida)
    if saida.is_dir():
        (saida/'finalizacao.json').write_text(json.dumps({
            'execucao': execucao, 'pipeline_returncode': codigo_pipeline,
            'metricas_returncode': codigo_metricas,
            'status': 'concluida' if codigo_pipeline == codigo_metricas == 0 else 'com_pendencias',
        }, indent=2) + '\n', encoding='utf-8')


def carregar_config(arquivo: Path) -> dict:
    import yaml

    config = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    campos = {"modo", "casos", "estrategias", "k", "catalogo", "perfil_sast",
              "baseline_testes", "semgrep_bin", "saida_base"}
    opcionais = {"politica_validacao", "mapa_testes", "cache_validacao", "repeticao_api", "cobertura_funcional", "modelo"}
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
    for campo in opcionais - {'mapa_testes','cobertura_funcional','modelo'}:
        if campo in config:
            permitidos = {'politica_validacao': ('historica_v1','otimizada_v1','relacionada_v1','relacionada_v2'),
                          'cache_validacao': ('desligado','leitura','leitura-escrita'),
                          'repeticao_api': ('ampla','seletiva-experimental')}
            if config[campo] not in permitidos[campo]:
                raise ValueError(f'{campo} inválido')
    if config.get('politica_validacao') in ('otimizada_v1','relacionada_v1','relacionada_v2') and not config.get('mapa_testes'):
        raise ValueError('Política de testes relacionados requer mapa_testes')
    if config.get('mapa_testes'):
        config['mapa_testes'] = (RAIZ / config['mapa_testes']).resolve()
        if not config['mapa_testes'].is_file():
            raise ValueError('Mapa de testes ausente')
    if config.get('politica_validacao')=='relacionada_v2' and not config.get('cobertura_funcional'):
        raise ValueError('relacionada_v2 requer cobertura_funcional')
    if config.get('cobertura_funcional'):
        if config.get('politica_validacao')!='relacionada_v2':raise ValueError('Cobertura requer relacionada_v2')
        config['cobertura_funcional']=(RAIZ/config['cobertura_funcional']).resolve()
        if not config['cobertura_funcional'].is_file():raise ValueError('Revisão de cobertura ausente')
    if "modelo" in config:
        validar_modelo(config["modelo"])
    return config


def montar_comandos(config: dict, python: str, execucao: str) -> tuple[list[str], list[str]]:
    saida = config["saida_base"] / execucao
    pipeline = [python, str(RAIZ / "src/pipeline/orquestracao/campanha.py"),
                "--execucao", execucao, "--catalogo", str(config["catalogo"]),
                "--perfil-sast", str(config["perfil_sast"]), "--saida", str(saida),
                "--casos", ",".join(config["casos"]),
                "--estrategias", ",".join(config["estrategias"]), "--k", str(config["k"]),
                "--semgrep-bin", str(config["semgrep_bin"]),
                "--baseline-testes", str(config["baseline_testes"])]
    for campo in ("politica_validacao", "mapa_testes", "cache_validacao", "repeticao_api", "cobertura_funcional", "modelo"):
        if config.get(campo) is not None:
            pipeline.extend(["--" + campo.replace("_", "-"), str(config[campo])])
    if config["modo"] == "preflight":
        pipeline.append("--somente-preflight")
    elif config["modo"] == "dry-run":
        pipeline.append("--dry-run")
    metricas = [python, str(RAIZ / "scripts/relatorios/consolidar_metricas.py"),
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
    parser.add_argument("--modelo", choices=MODELOS_OPENAI,
                        help="Seleciona o modelo OpenAI; prioridade sobre YAML e .env")
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
        if args.modelo:
            argumentos.extend(["--modelo", args.modelo])
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
        if args.modelo:
            config["modelo"] = args.modelo
        execucao = f"AMP_{config['modo'].upper().replace('-', '_')}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
        pipeline, metricas = montar_comandos(config, sys.executable, execucao)
        if args.mostrar_comando:
            print(shlex.join(pipeline))
            print(shlex.join(metricas))
            return 0
        print(f"Modo: {config['modo']} | Casos: {', '.join(config['casos'])} | K={config['k']}", flush=True)
        if config.get("modelo"):
            print(f"Modelo OpenAI selecionado: {config['modelo']}", flush=True)
        print(f"Resultados: {config['saida_base'] / execucao}", flush=True)
        if config["modo"] == "real":
            print("Execução real: chamadas à LLM sujeitas aos limites acumulados do .env.", flush=True)
        # A consolidação é independente do código de saída da campanha.
        try:
            codigo_pipeline = subprocess.run(pipeline, cwd=RAIZ).returncode
        except KeyboardInterrupt:
            codigo_pipeline = 130
        saida = config['saida_base'] / execucao
        consolidavel = tem_dados_consolidaveis(saida, config['modo'], execucao)
        codigo_metricas = None
        if codigo_pipeline == 0 or consolidavel:
            if codigo_pipeline:
                print('Campanha interrompida/com pendências; consolidando os dados disponíveis.', flush=True)
            codigo_metricas = subprocess.run(metricas, cwd=RAIZ).returncode
            if codigo_metricas == 0:
                print(f"Métricas: {config['saida_base'] / (execucao + '_METRICAS')}")
        registrar_finalizacao(saida, execucao, codigo_pipeline, codigo_metricas)
        if codigo_pipeline or codigo_metricas != 0:
            print('Execução com pendências; consulte os artefatos e a finalização.', file=sys.stderr)
        codigo = codigo_pipeline or codigo_metricas or 0
        return codigo if codigo >= 0 else 1
    except (ValueError, OSError, ImportError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
