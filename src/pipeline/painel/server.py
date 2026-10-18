"""Servidor HTTP restrito ao computador local, sem dependências web adicionais."""
import argparse
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit

from pipeline.painel.controller import Controle

RAIZ = Path(__file__).resolve().parents[3]


def handler(controle, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def responder(self, codigo, conteudo, tipo='application/json; charset=utf-8'):
            dados = json.dumps(conteudo, ensure_ascii=False).encode() if isinstance(conteudo, dict) else conteudo
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(dados)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(dados)

        def autorizado(self):
            # Recusa páginas de terceiros tentando controlar o processo local.
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                return False
            origem = self.headers.get('Origin')
            return origem is None or origem == f'http://{host}'

        def do_GET(self):
            if not self.autorizado():
                return self.responder(403, {'erro': 'Acesse pelo endereço 127.0.0.1 informado no terminal'})
            url = urlsplit(self.path)
            try:
                if url.path == '/api/status':
                    selecao = parse_qs(url.query).get('selecao', [None])[0]
                    return self.responder(200, controle.snapshot(selecao))
                if url.path == '/api/historico':
                    return self.responder(200, {'execucoes': controle.historico()})
                if url.path == '/api/token':
                    return self.responder(200, {'token': token})
                arquivos = {'/': ('index.html', 'text/html; charset=utf-8'),
                            '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                            '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if url.path not in arquivos:
                    return self.responder(404, {'erro': 'Página não encontrada'})
                nome, tipo = arquivos[url.path]
                self.responder(200, (RAIZ / 'frontend/painel' / nome).read_bytes(), tipo)
            except (ValueError, OSError) as exc:
                self.responder(400, {'erro': str(exc)})

        def do_POST(self):
            if not self.autorizado() or not secrets.compare_digest(self.headers.get('X-Painel-Token', ''), token):
                return self.responder(403, {'erro': 'Requisição não autorizada'})
            try:
                tamanho = int(self.headers.get('Content-Length', '0'))
                if not 0 < tamanho <= 1024:
                    raise ValueError('Corpo inválido')
                dados = json.loads(self.rfile.read(tamanho))
                if not isinstance(dados, dict):
                    raise ValueError('Objeto JSON esperado')
                if self.path == '/api/iniciar':
                    return self.responder(200, {'execucao': controle.iniciar(dados.get('modo'))})
                if self.path == '/api/parar':
                    controle.parar()
                    return self.responder(200, {'status': 'parando'})
                self.responder(404, {'erro': 'Operação desconhecida'})
            except (ValueError, OSError) as exc:
                self.responder(400, {'erro': str(exc)})
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--porta', type=int, default=8765)
    # 0.0.0.0 só dentro do container (docs/docker.md): o compose publica a porta
    # apenas em 127.0.0.1 do host, e o cabeçalho Host continua exigindo 127.0.0.1.
    parser.add_argument('--endereco', choices=('127.0.0.1', '0.0.0.0'), default='127.0.0.1',
                        help='Endereço de escuta; 0.0.0.0 somente dentro do container Docker')
    parser.add_argument('--config', type=Path, default=RAIZ / 'config/execucao.yaml')
    args = parser.parse_args(argv)
    if not 1 <= args.porta <= 65535:
        parser.error('Porta fora do intervalo 1–65535')
    cache = RAIZ / '.cache/painel'
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / 'servidor.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, 'Outro painel ou processo supervisionado ainda está ativo.\n')
        controle = Controle(RAIZ, args.config, lock.fileno())
        try:
            controle.configuracao()
            servidor = ThreadingHTTPServer((args.endereco, args.porta), handler(controle, secrets.token_urlsafe(32)))
        except (ValueError, OSError) as exc:
            parser.exit(1, f'ERRO: {exc}\n')
        print(f'Painel: http://127.0.0.1:{args.porta}', flush=True)
        print('Nenhum pipeline é iniciado ao abrir o painel. Ctrl+C solicita parada segura.', flush=True)
        try:
            servidor.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            print('\nEncerrando: aguardando a etapa/tentativa atual e a restauração da worktree.', flush=True)
        finally:
            servidor.server_close()
            controle.encerrar()
    return 0
