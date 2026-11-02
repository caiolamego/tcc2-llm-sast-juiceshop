"""Controle positivo funcional: substituir $where por seleção estruturada do produto."""
import hashlib
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.experimento.validar_controles_cobertura import conferir_checkout
from pipeline.etapas.e06_aplicacao.worktrees import reservar_execucao
from pipeline.etapas.e02_catalogo.catalogo import carregar
from pipeline.etapas.e07_validacao import cobertura
from pipeline.etapas.e07_validacao.execucao_cobertura import executar_grupo


def main():
    reservar_execucao(ROOT)
    wt = ROOT / 'workspace/wt-1'
    catalogo = carregar(ROOT / 'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    conferir_checkout(wt, catalogo.commit)
    rev, mapa = ROOT / 'config/cobertura_funcional_v6.yaml', ROOT / 'config/mapa_testes_relacionados_v7.yaml'
    data = cobertura.carregar(rev, mapa, wt, catalogo)
    output = Path(__file__).resolve().parent.parent / 'consulta_estruturada'
    output.mkdir(parents=True, exist_ok=False)
    source = wt / 'routes/chat.ts'
    original = source.read_bytes()
    before = "return await db.reviewsCollection.find({ $where: 'this.product == ' + productId }) as Review[]"
    after = 'return await db.reviewsCollection.find({ product: productId }) as Review[]'
    if original.decode().count(before) != 1:
        raise ValueError('Âncora ausente/ambígua')
    changed = original.decode().replace(before, after).encode()
    report = {'schema_versao': '1.0', 'status': 'parcial', 'chamadas_llm': 0,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'original_sha256': hashlib.sha256(original).hexdigest(),
              'alterado_sha256': hashlib.sha256(changed).hexdigest(),
              'cobertura': cobertura.identidade(data, rev, mapa)}
    try:
        healthy = executar_grupo(wt, 'chat_reviews', data['grupos']['chat_reviews'], output / 'original', lock_api=threading.Lock())
        if not healthy['comparavel'] or healthy['falhos']:
            raise ValueError('Original não aprovado')
        conferir_checkout(wt, catalogo.commit)
        source.write_bytes(changed)
        try:
            result = executar_grupo(wt, 'chat_reviews', data['grupos']['chat_reviews'], output / 'estruturado', lock_api=threading.Lock())
        finally:
            if source.read_bytes() != changed:
                raise RuntimeError('Alteração desconhecida; restauração recusada')
            source.write_bytes(original)
        conferir_checkout(wt, catalogo.commit)
        report.update(aprovado=bool(result['comparavel'] and not result['falhos']),
                      testes=len(result['testes']), restaurado=source.read_bytes() == original)
        if not report['aprovado']:
            raise ValueError('Consulta estruturada reprovada')
        report['status'] = 'concluido'
    finally:
        report['artefatos_sha256'] = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(output.rglob('*')) if p.is_file()}
        (output / 'resultado.json').write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print('Consulta estruturada: nove testes aprovados; original restaurado.', flush=True)


if __name__ == '__main__':
    main()
