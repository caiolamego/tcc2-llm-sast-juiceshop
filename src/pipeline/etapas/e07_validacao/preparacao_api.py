"""Pré-condições locais da API, sem importar/iniciar o servidor Juice Shop."""
from pathlib import Path
import shutil
import socket
import tempfile

from pipeline.comum.identidade import digest
from pipeline.etapas.e07_validacao.selecao import interno

OBRIGATORIOS = ('build/server.js', 'frontend/dist/frontend/index.html',
                'frontend/dist/frontend/styles.css', 'frontend/dist/frontend/main.js',
                'frontend/dist/frontend/polyfills.js')


def inventario(wt):
    wt = Path(wt).resolve()
    nomes = list(OBRIGATORIOS)
    chunks = sorted((wt/'frontend/dist/frontend').glob('hacking-instructor-*.js'))
    nomes.extend(p.relative_to(wt).as_posix() for p in chunks)
    ausentes = [] if chunks else ['frontend/dist/frontend/hacking-instructor-*.js']
    hashes = {}
    for nome in nomes:
        path = interno(wt, nome)
        if not path.is_file() or not path.stat().st_size:
            ausentes.append(nome)
        else:
            hashes[nome] = digest(path)
    return {'arquivos_sha256': hashes, 'ausentes': sorted(ausentes)}


def conferir(wt, verificar_porta=True):
    data = inventario(wt)
    if data['ausentes']:
        raise ValueError(f'Preparação API incompleta em {Path(wt).name}: '+', '.join(data['ausentes']))
    if verificar_porta:
        from pipeline.etapas.e07_validacao.camadas import porta_t4
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', porta_t4(Path(wt))))
            except OSError as exc:
                raise ValueError(f'Porta API indisponível em {Path(wt).name}') from exc
    return data


def preparar(origem, destino):
    """Copia árvores ausentes com isolamento; nunca substitui conteúdo existente."""
    origem, destino = Path(origem).resolve(), Path(destino).resolve()
    referencia = conferir(origem, False)
    criados = []
    for nome in ('build', 'frontend/dist'):
        source, target = interno(origem, nome), interno(destino, nome)
        if target.exists():
            continue
        # Recusar escapes antes de copiar inclusive links internos das árvores.
        for path in source.rglob('*'):
            if path.is_symlink():
                raise ValueError('Árvore de preparação contém symlink: '+str(path))
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix='.preparo_api_', dir=target.parent))
        try:
            shutil.copytree(source, temporary/'conteudo')
            from pipeline.etapas.e09_metricas.publicacao import _promover_exclusivo
            _promover_exclusivo(temporary/'conteudo', target)
            criados.append(nome)
        finally:
            shutil.rmtree(temporary)
    atual = conferir(destino, False)
    if atual != referencia:
        raise ValueError('Artefatos API existentes divergem da referência; substituição recusada')
    return {'diretorios_criados': criados, **atual}
