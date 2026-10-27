"""Cache local por conteúdo, com lock entre processos e publicação atômica."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from uuid import uuid4

from pipeline.comum.identidade import hash_json, digest


class CacheEvidencias:
    def __init__(self, raiz, modo='desligado', parar=lambda: False):
        self.raiz, self.modo, self.parar = Path(raiz), modo, parar

    @contextmanager
    def _lock(self, path):
        with path.open('a') as stream:
            inicio = time.monotonic()
            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if self.parar():
                        raise InterruptedError('Parada durante espera de cache')
                    if time.monotonic() - inicio > 900:
                        raise TimeoutError('Espera de cache excedeu 900 s')
                    time.sleep(.05)
            try:
                yield time.monotonic() - inicio
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def obter(self, componente, identidade, calcular, conferir, elegivel, origem):
        conferir_original = conferir
        def conferir():
            try:return conferir_original()
            except (ValueError,OSError):return False
        inicio = time.monotonic()
        chave = hash_json(identidade)
        meta = {'componente': componente, 'chave': chave, 'hit': False,
                'origem': origem, 'espera_lock_s': 0., 'motivo': 'desligado'}
        if self.modo == 'desligado':
            return calcular(), meta
        pasta = self.raiz / componente
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta/chave
        with self._lock(pasta/(chave+'.lock')) as espera:
            meta['espera_lock_s'] = espera
            meta['motivo'] = 'ausente'
            if destino.exists():
                try:
                    if destino.is_symlink(): raise ValueError('Symlink de cache')
                    manifest_path, result_path = destino/'manifesto.json', destino/'resultado.json'
                    if manifest_path.is_symlink() or result_path.is_symlink(): raise ValueError('Symlink em cache')
                    manifest = json.loads(manifest_path.read_text())
                    if (manifest['schema_versao'] != '1.0' or manifest['identidade'] != identidade
                            or manifest['sha256'] != digest(result_path)):
                        raise ValueError('Hash/identidade de cache divergente')
                    value = json.loads(result_path.read_text())
                    if not elegivel(value) or not conferir():
                        raise ValueError('Evidência ou alvo não reutilizável')
                    meta.update(hit=True, motivo='verificado', origem=manifest['origem'],
                                evidencia_sha256=manifest['sha256'], lookup_s=time.monotonic()-inicio)
                    return value, meta
                except (ValueError, OSError, KeyError, TypeError, AttributeError):
                    meta['motivo'] = 'entrada_invalida'
                    if self.modo == 'leitura-escrita':
                        destino.rename(pasta/(chave+'.invalido-'+uuid4().hex))
            meta['lookup_s'] = time.monotonic()-inicio
            value = calcular()
            if self.modo == 'leitura-escrita' and elegivel(value) and conferir():
                tmp = Path(tempfile.mkdtemp(prefix=chave+'.tmp-', dir=pasta))
                try:
                    result_path = tmp/'resultado.json'
                    result_path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n')
                    manifest = {'schema_versao':'1.0', 'identidade': identidade, 'sha256': digest(result_path), 'origem':origem}
                    (tmp/'manifesto.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True)+'\n')
                    if not conferir(): raise ValueError('Entrada alterada durante publicação de cache')
                    if not destino.exists(): os.rename(tmp, destino)
                    meta['publicado'] = True
                    meta['evidencia_sha256'] = manifest['sha256']
                finally:
                    if tmp.exists(): shutil.rmtree(tmp)
            elif not elegivel(value):
                meta['motivo'] = 'evidencia_nao_reutilizavel'
            elif not conferir():
                meta['motivo'] = 'estado_alterado_na_validacao'
            return value, meta
