"""Supervisiona somente os processos iniciados pelo painel; não executa ao importar."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from uuid import uuid4

from executar import carregar_config, montar_comandos


def segundos(valor):
    return valor if type(valor) in (int, float) and math.isfinite(valor) and valor >= 0 else None


def resumo_tentativa(linha):
    tempos = {nome: segundos(linha.get(campo)) for nome, campo in (
        ('llm', 'duracao_llm_s'), ('sast', 'duracao_sast_s'),
        ('validacao', 'duracao_validacao_s'), ('total', 'duracao_total_s'))}
    estimado = tempos['total'] is None
    if estimado:
        partes = [tempos[n] for n in ('llm', 'sast', 'validacao')]
        # Não tratar etapas ausentes como zero ou chamar esta soma de tempo total medido.
        tempos['total'] = sum(partes) if all(v is not None for v in partes) else None
    return {**{k:linha.get(k) for k in ('provedor','modelo','custo_usd','espera_inferencia_s','requisicao_s')},
            'caso': linha.get('caso_id'), 'arquivo': linha.get('arquivo'),
            'estrategia': linha.get('estrategia_prompt'),
            'classificacao': linha.get('classificacao_final'),
            'R': linha.get('R'), 'F': linha.get('F_criterio', linha.get('F')), 'M': linha.get('M'),
            'cache': linha.get('do_cache', False), 'tempos': tempos,
            'cache_validacao': linha.get('cache_validacao', {}),
            'politica_validacao': linha.get('politica_validacao', 'historica_v1'),
            'tempos_medicao': linha.get('tempos_medicao', {}),
            'etapas_validacao': linha.get('etapas_validacao', []),
            'motivos_indeterminacao': linha.get('motivos_indeterminacao', []),
            'versao_comparador': linha.get('versao_comparador', 'blocos_unicos_v1'),
            'falhas_contexto_sast': linha.get('falhas_contexto_sast', {}),
            'cobertura_detalhada': linha.get('cobertura_detalhada'),
            'cobertura_funcional': linha.get('cobertura_funcional'),
            'total_estimado': estimado}


class Controle:
    def __init__(self, raiz: Path, config: Path, lock_fd=None):
        self.raiz, self.config = raiz.resolve(), config.resolve()
        self.lock_fd = lock_fd
        self.lock = threading.RLock()
        self.worker = None
        self.atual = None
        self.fechando = False

    def caminho_local(self, caminho):
        path = Path(caminho).resolve()
        if not path.is_relative_to(self.raiz / 'outputs'):
            raise ValueError('Os resultados do painel devem ficar dentro de outputs/')
        return path

    def configuracao(self):
        config = carregar_config(self.config)
        self.caminho_local(config['saida_base'])
        return config

    def iniciar(self, modo):
        if modo not in ('real', 'dry-run', 'preflight'):
            raise ValueError('Modo inválido')
        with self.lock:
            if self.fechando or (self.worker and self.worker.is_alive()):
                raise ValueError('Já há uma execução ativa ou o painel está encerrando')
            config = self.configuracao()
            config['modo'] = modo
            ident = f"AMP_PAINEL_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
            controle = self.raiz / '.cache/painel' / ident
            controle.mkdir(parents=True, exist_ok=False)
            logs = self.raiz / 'outputs/painel'
            logs.mkdir(parents=True, exist_ok=True)
            self.atual = {'execucao': ident, 'modo': modo, 'status': 'executando',
                          'inicio': time.time(), 'fim': None, 'etapa': 'pipeline',
                          'casos': config['casos'], 'estrategias': config['estrategias'],
                          'k': config['k'],
                          'politica_validacao':config.get('politica_validacao','historica_v1'),
                          'cache_validacao':config.get('cache_validacao','desligado'),
                          'repeticao_api':config.get('repeticao_api','ampla'),
                          'saida': str(config['saida_base'] / ident),
                          'log': str(logs / f'{ident}.console.log'),
                          'parada': str(controle / 'parar'), 'erro': None}
            self.worker = threading.Thread(target=self._executar, args=(config, self.atual),
                                           name='pipeline-painel', daemon=False)
            self.worker.start()
            return ident

    def _executar(self, config, estado):
        comandos = montar_comandos(config, sys.executable, estado['execucao'])
        comandos[0].extend(['--arquivo-parada', estado['parada']])
        ambiente = {**os.environ, 'PYTHONUNBUFFERED': '1', 'NO_COLOR': '1', 'TERM': 'dumb'}
        try:
            with Path(estado['log']).open('w', encoding='utf-8') as log:
                for etapa, comando in zip(('pipeline', 'metricas'), comandos):
                    # Uma execução interrompida continua disponível nos registros parciais.
                    if Path(estado['parada']).exists() and etapa == 'metricas':
                        break
                    with self.lock:
                        estado['etapa'] = etapa
                    log.write(f'\n--- {etapa} ---\n')
                    log.flush()
                    proc = subprocess.Popen(comando, cwd=self.raiz, env=ambiente,
                                            stdout=log, stderr=subprocess.STDOUT,
                                            start_new_session=True,
                                            pass_fds=(() if self.lock_fd is None else (self.lock_fd,)))
                    codigo = proc.wait()
                    if codigo:
                        raise RuntimeError(f'{etapa} terminou com código {codigo}')
            with self.lock:
                estado['status'] = 'interrompida' if Path(estado['parada']).exists() else 'finalizada'
        except Exception as exc:
            with self.lock:
                estado['status'], estado['erro'] = 'falhou', str(exc)
        finally:
            with self.lock:
                estado['fim'] = time.time()
            Path(estado['log']).with_suffix('.estado.json').write_text(
                json.dumps(estado, ensure_ascii=False, indent=2), encoding='utf-8')

    def parar(self):
        with self.lock:
            if not self.worker or not self.worker.is_alive():
                raise ValueError('Nenhuma execução ativa iniciada por este painel')
            Path(self.atual['parada']).touch(exist_ok=True)
            self.atual['status'] = 'parando'

    def encerrar(self):
        with self.lock:
            self.fechando = True
            worker = self.worker
            if worker and worker.is_alive():
                self.parar()
        if worker:
            worker.join()  # Não abandona filhos nem worktrees com patches aplicados.

    def historico(self):
        encontrados = []
        for arquivo in (self.raiz / 'outputs').rglob('contrato_execucao.json'):
            try:
                path = self.caminho_local(arquivo)
                contrato = json.loads(path.read_text(encoding='utf-8'))
                encontrados.append({'caminho': str(path.parent.relative_to(self.raiz / 'outputs')),
                                     'execucao': contrato['execucao'], 'modo': contrato.get('modo')})
            except (ValueError, OSError, KeyError):
                continue
        return sorted(encontrados, key=lambda r: r['execucao'], reverse=True)

    def tentativas(self, pasta):
        arquivo = self.caminho_local(Path(pasta) / 'resultados_consolidados/execucoes.jsonl')
        linhas, avisos = [], []
        if arquivo.is_file():
            with arquivo.open(encoding='utf-8') as stream:
                for numero, linha in enumerate(stream, 1):
                    try:
                        linhas.append(resumo_tentativa(json.loads(linha)))
                    except (ValueError, TypeError, AttributeError):
                        avisos.append(f'Registro {numero} incompleto ou inválido; aguardando atualização.')
        return linhas, avisos

    def snapshot(self, selecao=None):
        with self.lock:
            atual = dict(self.atual) if self.atual else None
            ativo = bool(self.worker and self.worker.is_alive())
        config = atual if atual and ativo else self.configuracao()
        pasta = self.caminho_local(self.raiz / 'outputs' / selecao) if selecao else (
            Path(atual['saida']) if atual else None)
        tentativas, avisos = self.tentativas(pasta) if pasta else ([], [])
        logs = ''
        if atual and not selecao and Path(atual['log']).is_file():
            with Path(atual['log']).open('rb') as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 64000))
                logs = stream.read().decode('utf-8', errors='replace')
            logs = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', logs)
            logs = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[CHAVE OCULTADA]', logs)
        publico = None if not atual else {k: atual[k] for k in (
            'execucao', 'modo', 'status', 'inicio', 'fim', 'etapa', 'casos', 'estrategias', 'erro')}
        if publico:
            publico['decorrido_s'] = (atual['fim'] or time.time()) - atual['inicio']
        from pipeline.llm.provider import resumo_publico
        llm=resumo_publico(self.raiz/'.env')
        if pasta:
            contrato_path=self.caminho_local(pasta/'contrato_execucao.json')
            if contrato_path.is_file():
                inf=json.loads(contrato_path.read_text(encoding='utf-8')).get('inferencia')
                if isinstance(inf,dict):
                    llm={'provedor':inf.get('provedor'),'modelo':inf.get('modelo'),
                         'revisao':inf.get('cientifica',{}).get('revisao','')[:12],
                         'estado':'identidade_do_contrato','conexao':'não consultada agora'}
            eventos_path=self.caminho_local(pasta/'llm_operacional.jsonl')
            if eventos_path.is_file():
                try:
                    ultimo=json.loads(eventos_path.read_text(encoding='utf-8').splitlines()[-1])
                    llm['conexao']='verificada na sessão; não consultada agora' if ultimo.get('tipo')=='conexao_verificada' else 'falha/parada registrada na sessão'
                except (ValueError,IndexError):pass  # Escrita em andamento.
        return {'inferencia':llm, 'atual': publico, 'ativo': ativo, 'tentativas': tentativas, 'avisos': avisos,
                'log': logs, 'config': {'modo': config['modo'], 'casos': config['casos'],
                                       'estrategias': config['estrategias'], 'k': config['k'],
                                       'politica_validacao':config.get('politica_validacao','historica_v1'),
                                       'cache_validacao':config.get('cache_validacao','desligado'),
                                       'repeticao_api':config.get('repeticao_api','ampla')}}
