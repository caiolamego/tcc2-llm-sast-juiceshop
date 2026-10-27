"""Diagnóstico explícito: offline, conexão, smoke ou envio de prompt arquivado."""
from pathlib import Path
import sys
if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts import _bootstrap  # noqa: F401
import argparse
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e05_geracao_llm.protocolo_colab import read_json
from pipeline.etapas.e05_geracao_llm.provedor import criar_cliente, identidade_offline, provedor, texto_aplicavel, ErroOperacionalLLM
from pipeline.etapas.e05_geracao_llm.esquema import Correcao


def ler_prompt(path):
    path=Path(path).resolve()
    raw=path.read_bytes();data=read_json(path)
    messages=data.get('mensagens') if isinstance(data,dict) else None
    if not isinstance(messages,list) or not messages or not all(isinstance(m,dict) and set(m)=={'role','content'}
            and m['role'] in ('system','user','assistant') and isinstance(m['content'],str) for m in messages):
        raise ValueError('Arquivo não contém mensagens de prompt válidas')
    # Mesma serialização do builder; não modificar mensagens nem anexar instruções.
    reconstructed=[{'role':m['role'],'content':m['content']} for m in messages]
    prompt_hash=hashlib.sha256(json.dumps(reconstructed,ensure_ascii=False).encode()).hexdigest()
    if data.get('hash_prompt')!=prompt_hash:
        raise ValueError('Hash do prompt arquivado inconsistente')
    return raw,messages,prompt_hash


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--modo', choices=('offline','conexao','smoke','prompt','mensagem'), default='offline')
    ap.add_argument('--env',type=Path,help='Arquivo dotenv; padrão: .env do repositório')
    ap.add_argument('--prompt-arquivo',type=Path,help='JSON arquivado com mensagens e hash_prompt; obrigatório em modo prompt')
    ap.add_argument('--saida',type=Path,help='Diretório novo para modo prompt/mensagem; padrão: outputs/diagnosticos_llm/<ID>')
    ap.add_argument('--mensagem',help='Texto a enviar no modo mensagem; padrão: teste')
    args=ap.parse_args(argv)
    if args.modo=='prompt' and not args.prompt_arquivo:ap.error('--modo prompt requer --prompt-arquivo')
    if args.modo!='prompt' and args.prompt_arquivo:ap.error('--prompt-arquivo requer --modo prompt')
    if args.modo not in ('prompt','mensagem') and args.saida:ap.error('--saida requer --modo prompt ou mensagem')
    if args.modo!='mensagem' and args.mensagem is not None:ap.error('--mensagem requer --modo mensagem')
    if args.modo=='mensagem' and args.mensagem is not None and not args.mensagem.strip():ap.error('--mensagem não pode ser vazia')
    client=None;output=None;report={}
    try:
        identity=identidade_offline(args.env)
        if identity['provedor']=='openai':
            from pipeline.etapas.e05_geracao_llm.cliente_openai import ConfigLLM
            ConfigLLM.do_env(args.env or RAIZ_REPO/'.env')
        report={'tipo':'diagnostico_llm','modo':args.modo,'identidade':identity,'geracoes':0}
        if args.modo in ('prompt','mensagem'):
            if identity['provedor']!='colab':raise ValueError('Diagnóstico de geração requer Colab')
            if args.modo=='prompt':
                raw,messages,prompt_hash=ler_prompt(args.prompt_arquivo)
            else:
                messages=[{'role':'user','content':args.mensagem if args.mensagem is not None else 'teste'}]
                prompt_hash=hashlib.sha256(json.dumps(messages,ensure_ascii=False).encode()).hexdigest()
                raw=(json.dumps({'mensagens':messages,'hash_prompt':prompt_hash},ensure_ascii=False,indent=2)+'\n').encode()
            prefix='PROMPT_' if args.modo=='prompt' else 'MENSAGEM_'
            ident=prefix+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid4().hex[:8]
            candidate=(args.saida or RAIZ_REPO/'outputs/diagnosticos_llm'/ident).resolve()
            if candidate.exists() or candidate==RAIZ_REPO or (args.prompt_arquivo is not None and args.prompt_arquivo.resolve().is_relative_to(candidate)):
                raise ValueError('Saída existente ou sobreposta ao prompt')
            # mkdir exclusivo reserva uma saída nova; nenhum artefato anterior é substituído.
            candidate.mkdir(parents=True,exist_ok=False)
            output=candidate
            (output/'prompt.json').write_bytes(raw)
            report.update(tipo='diagnostico_prompt_arquivado' if args.modo=='prompt' else 'diagnostico_mensagem_livre',hash_prompt=prompt_hash,
                          arquivo_prompt_sha256=hashlib.sha256(raw).hexdigest(),aplica_patch=False,
                          executa_sast=False,executa_testes=False)
            print('Enviando somente '+('o prompt arquivado' if args.modo=='prompt' else 'a mensagem de diagnóstico')+'. Resposta/erro serão salvos em: '+str(output),flush=True)
        if args.modo!='offline':
            if identity['provedor']!='colab':raise ValueError('Conexão/geração deste comando requer LLM_PROVIDER=colab')
            client=criar_cliente(args.env)
            report['conexao']=client.conferir_conexao()
            if args.modo in ('smoke','prompt','mensagem'):
                if args.modo=='smoke':
                    example={'vulnerabilidade_identificada':'exemplo sintético','causa_da_vulnerabilidade':'não aplicável',
                             'estrategia_de_correcao':'nenhuma','edicoes':[], 'justificativa_tecnica':'diagnóstico sem código alvo',
                             'limitacoes_da_correcao':'não é tentativa do experimento'}
                    messages=[{'role':'user','content':'Devolva este objeto JSON sem alterações: '+json.dumps(example,ensure_ascii=False)}]
                r=client.gerar(messages)
                report.update(geracoes=r.chamadas_enviadas,resposta=r.to_dict())
                if output:
                    from pipeline.etapas.e05_geracao_llm.cliente_colab import atomic_json
                    atomic_json(output/'resposta.json',r.to_dict())
                    if args.prompt_arquivo is not None and args.prompt_arquivo.read_bytes()!=raw:raise ValueError('Prompt alterado durante o diagnóstico')
                Correcao.model_validate_json(texto_aplicavel(r))
        if output:
            from pipeline.etapas.e05_geracao_llm.cliente_colab import atomic_json
            atomic_json(output/'resultado.json',report)
            print(json.dumps({'status':'resposta_valida','saida':str(output),'geracoes':r.chamadas_enviadas,
                              'do_cache':r.do_cache,'latencia_s':r.latencia_s,'finish_reason':r.finish_reason,
                              **({'conteudo':r.conteudo} if args.modo=='mensagem' else {})},ensure_ascii=False,indent=2))
        else:print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
        return 0
    except Exception as exc:
        error={'erro':str(exc) if isinstance(exc,ErroOperacionalLLM) else 'Diagnóstico falhou; confira configuração, identidade, arquivo e disponibilidade',
               'tipo':type(exc).__name__}
        if output:
            from pipeline.etapas.e05_geracao_llm.cliente_colab import atomic_json
            # O contador Colab guarda envios reservados mesmo quando não há resposta.
            if 'resposta' not in report:
                report['geracoes']=None
                report['nota_envios']='Erro não implica zero envios; consulte o contador Colab persistente.'
            report.update(status='falhou',**error)
            atomic_json(output/'resultado.json',report)
            error['saida']=str(output)
        print(json.dumps(error,ensure_ascii=False),file=sys.stderr)
        return 1
    finally:
        if client is not None and hasattr(client,'http'):client.http.close()


if __name__=='__main__':raise SystemExit(main())
