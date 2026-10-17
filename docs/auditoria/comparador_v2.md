# Comparador v2 — entrega e calibração em 17/10/2026

Novas execuções ampliadas usam `ocorrencias_contexto_v2`. O comparador
`blocos_unicos_v1`, os registros anteriores e os scans arquivados permanecem
preservados. O catálogo de 78 ocorrências, as regras e os prompts não mudaram.

## O que mudou

O pareamento continua separado por regra e arquivo, um para um. Primeiro usa
coordenadas em arquivos inalterados e blocos únicos de linhas, como na v1.
Para os remanescentes em arquivos JS/TS alterados, acrescenta:

1. Blocos únicos de tokens, que toleram alterações de espaços e comentários.
2. Foco com sequência de tokens única nas duas fontes e mesmo escopo sintático.
3. Chamada única no mesmo escopo de função, com o mesmo callee, aridade e papel
   do foco (chamada ou posição do argumento). A chamada deve ser única em todo
   o escopo, inclusive entre chamadas não sinalizadas. Seu callee precisa de
   âncora lexical única ou de mapeamento em bloco único de tokens.

Os dois últimos critérios não usam apenas “um alerta antes e um depois”. Escopos
repetidos, chamadas duplicadas e propostas concorrentes impedem o pareamento.
Cada par informa o método e a evidência utilizada. Esses critérios identificam
persistência sintática; não demonstram equivalência de comportamento ou segurança.
Alterações de funções, nomes, aridade ou contexto ainda podem ficar indeterminadas.

A AST vem do compilador TypeScript instalado na worktree. O adaptador Node lê
texto e não importa nem executa o código analisado. Colunas e offsets são
conferidos em bytes UTF-8, incluindo CRLF. Parser ausente, sintaxe não reconhecida
ou linguagem sem suporte preservam o pareamento v1 e registram a limitação.
Coordenadas contraditórias impedem conclusões positivas na cobertura afetada.

A política anterior de parsing/timeout continua vigente: diagnósticos equivalentes
em arquivos inalterados dão cobertura limitada; falhas novas, arquivos alterados
com parsing e falhas operacionais impedem conclusões positivas afetadas. Os
remanescentes dos dois lados continuam ambíguos; não se usa saldo de contagens.

O hash do adaptador `.cjs` integra a implementação do contrato/cache. O ambiente
contratado já inclui Node, versão TypeScript e conteúdo instalado das dependências;
as comparações registram também hashes do módulo TypeScript e do adaptador.
Alterações do parser durante sua leitura são recusadas. O scan pode ser reutilizado,
mas a comparação da ocorrência é executada novamente.

## Reanálise offline

Foram utilizados os mesmos scans e códigos arquivados, sem Semgrep novo, LLM,
patches em worktrees ou execução de testes funcionais. As entradas e os hunks dos
oito patches foram conferidos; o diff é reconstruído somente em memória para
conferir sua correspondência ao código arquivado. A ferramenta de reanálise
recusa patches com múltiplos arquivos; o comparador do pipeline aceita todos os
arquivos alterados fornecidos pelo aplicador normal.

| Conjunto | Quantidade | Indeterminados v1 | Indeterminados v2 |
|---|---:|---:|---:|
| Referências pedagógicas | 63 alternativas | 28 | 6 |
| Patches da execução anterior | 8 tentativas | 4 | 0 |

Nas 17 alternativas marcadas corretas: 16 têm R=1/M_fixture=1; `registerAdmin`
mantém R=0/M_fixture=1. Nas 46 incorretas: 21 têm R=1/M_fixture=1, 18 têm
R=0/M_fixture=1, uma R=1/M_fixture=0 e seis permanecem indeterminadas.

As seis ambiguidades restantes estão em alternativas incorretas de
`accessLogDisclosure`, `directoryListing`, `redirect`, `resetPasswordMorty`
(duas) e `restfulXss`. A classificação pedagógica não foi usada pelo comparador.
Não foram criadas exceções por desafio ou caso.

Nos oito patches de `AMP_PAINEL_20261017T030957Z_2679b8a6`:

- Login, P1–P4: R=1/M=1, como na v1.
- KeyServer, P1–P4: R=0/M=1. A chamada `res.sendFile` permanece sinalizada,
  embora o argumento tenha sido reescrito. Isso não comprova vulnerabilidade
  explorável nem ausência de mitigação: significa que o alerta persiste.

Os F originais são apenas transcritos na reanálise. Não se recalculam aceites ou
métricas antigas a partir destes resultados. M_fixture das referências isoladas
não representa M global do Juice Shop. Os oito patches usam o scan global arquivado.

Este conjunto foi observado durante a implementação e é **calibração**, não teste
independente nem estimativa de precisão/recall. A validação em outros casos ainda
é necessária antes da campanha final.

## Associações e controles negativos

[Seis revisões documentais](../../config/revisoes_associacoes_v1.yaml) registram
mecanismos distintos, referências em outros arquivos, ocorrências fora do trecho,
montagem ambígua e ausência de referência. O arquivo tem versão, hash do catálogo
e evidências locais; seu leitor recusa duplicatas, IDs desconhecidos, hash
divergente e caminhos externos. Ele não modifica seleção, prompts ou catálogo.

Em `registerAdmin`, a solução restringe `role` a `customer`, enquanto a regra
continua sinalizando escrita gerada pelo finale. Não se exige que uma correção do
desafio elimine esse alerta mais amplo. Em `keyServer`, não existe codefix associado
que sirva como solução de referência desse caso.

As alternativas incorretas permanecem como controles: desaparecer um alerta não
autoriza um aceite. Por exemplo, a alternativa 3 de `loginAdmin` parametriza SQL,
mas usa a senha sem o hash esperado. A auditoria não mediu F dessa alternativa;
a descrição pedagógica indica a necessidade de teste funcional, não um valor F
retroativo. Um teste sintético verifica que R=1/M=1/F=0 resulta em TRV=0.
A definição de F e a parada estrita da cadeia continuam iguais às anteriores.

## Registro, painel e retomada

Novas tentativas registram versão do comparador, motivos separados para R/M,
arquivos com cobertura inconclusiva e falhas de contexto. O painel mostra a
explicação junto ao resultado e os detalhes ao passar o mouse. Resultados antigos
continuam com os valores originais; quando falta explicação estruturada, o painel
orienta consultar sua comparação arquivada.

Contratos novos identificam v2. Retomar uma saída com comparador/implementação
divergentes é recusado; use outra execução. As métricas continuam lendo os
contratos v1 e v2 sem reinterpretar medições anteriores. O lançador e o painel
geram nomes novos automaticamente. Nenhuma nova execução real foi iniciada nesta
entrega. Se o servidor do painel já estiver aberto com o código antigo, reinicie
`python painel.py` quando estiver ocioso e atualize o navegador.

## Reprodução e verificações

Ambiente: Python 3.12.3, Node v24.14.0 e TypeScript 6.0.3. Scans anteriores:
Semgrep 1.177.0, perfil congelado `ampliado_piloto_v1`, commit do alvo
`f915bddd82790d0f3018902d36ae9b4241a5f51f`.

```bash
make test-unit PYTHON=.venv/bin/python
.venv/bin/python scripts/audit/recompare_archived_scans.py \
  --execucao outputs/execucoes/AMP_PAINEL_20261017T030957Z_2679b8a6 \
  --saida outputs/auditoria_sast/comparador_v2_v1
```

O último destino já existe: para reproduzir, indique um diretório novo. O comando
publica com lock exclusivo, diretório temporário irmão, revalidação das entradas
e recusa de sobrescrita. Não registra novas tentativas de geração. `--help`
funciona fora da raiz e não requer serviços. Para outra execução arquivada,
forneça `--execucao`; o mesmo contrato/perfil/catálogo deve ser verificável.

Evidências: [resumo](../../outputs/auditoria_sast/comparador_v2_v1/resumo.json),
[comparação CSV](../../outputs/auditoria_sast/comparador_v2_v1/resultados.csv) e
[manifesto de hashes](../../outputs/auditoria_sast/comparador_v2_v1/manifesto.json).
Consulte também a [verificação final](../../outputs/auditoria_sast/comparador_v2_v1_verificacao.json).

Verificação concluída: 236 testes unitários passaram; os 76 arquivos da reanálise
foram reproduzidos byte a byte em outro destino; 2.576 artefatos anteriores
mantiveram seus hashes. `catalogo-alvo`, `wt-1` e `wt-2` estão limpos.
`git diff --check`, a sintaxe dos arquivos JavaScript e a prévia do lançador
passaram. Não houve commit, push ou chamada à LLM.
