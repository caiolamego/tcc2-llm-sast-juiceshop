# Feature 09 — Cache de respostas optativo e tolerância a falhas da LLM

**Status:** implementada e validada offline; veja o [relatório de entrega](ENTREGA.md).  
**Data:** 02/11/2026.  
**Escopo:** clientes OpenAI/Colab, fila de casos, execução pelo terminal/painel e consolidação offline.

## Problema e comportamento implementado

O cache local de respostas era utilizado automaticamente pelos clientes. No cliente
OpenAI, timeouts e falhas de conexão também ficavam fora das retentativas existentes.
Uma falha operacional Colab interrompia a fila inteira. Tanto `executar.py` quanto
o painel deixavam de chamar a consolidação de métricas quando a campanha terminava
com erro, inclusive se isso ocorresse no último caso.

Agora o cache de respostas está **desligado por padrão nos dois provedores**. Falhas
transitórias são tratadas com limites explícitos. Quando não há resposta utilizável,
o par caso/prompt fica registrado como pendência operacional e a fila segue conforme
a política abaixo. A consolidação ocorre mesmo após saída não zero, desde que existam
artefatos que possam ser validados. Isso inclui uma sessão sem nenhuma resposta.

Não há garantia de que uma API indisponível responderá. A execução pode terminar
com pendências e métricas parciais, sem exigir intervenção para iniciar a consolidação.
Erro fatal e orçamento continuam limitando novos envios.

## Cache e independência das chamadas

```dotenv
LLM_CACHE=desligado
```

Esse é o padrão quando a variável está ausente e está explícito em
[.env.example](../../../../.env.example). Variáveis exportadas têm precedência sobre
o arquivo local. `LLM_CACHE=leitura-escrita` permite ativar o comportamento de cache
explicitamente em replays; não deve ser usado na campanha que exige novas chamadas.
Outros valores são recusados.

Desligado, o cliente não lê nem grava respostas no cache, mesmo que exista uma entrada
antiga ou corrompida. Os arquivos antigos são preservados. O diretório `.cache/`
continua sendo usado para orçamento, reservas e travas; sua existência não indica
reutilização de resposta. O cache de validação SAST/funcional é uma opção independente.

O modo do cache integra a identidade de inferência no contrato. As implementações
também têm hashes, impedindo uma retomada silenciosa com outra política. Use uma nova
execução para esta versão, preservando os contratos históricos.

O cache local reutiliza uma resposta completa e é distinto do
[Prompt Caching do provedor OpenAI](https://developers.openai.com/api/docs/guides/prompt-caching),
que reaproveita processamento de prefixos. Esta feature desativa o cache **local de
respostas**. Novas requisições não garantem resultados diferentes ou determinismo absoluto.

## Mapa de erros e recuperação

| Situação | OpenAI | Colab | Efeito na campanha |
|---|---|---|---|
| Timeout ou conexão interrompida | Até três envios totais para o mesmo prompt | Mantém um envio de geração; não repete inferência cujo consumo é incerto | Esgotada a política, registra falha e segue para os demais pares |
| HTTP 408/409 ou 5xx | Até três envios totais | Registra o erro, sem reenviar automaticamente a mesma geração | Segue para os demais pares |
| HTTP 429 transitório | Até três envios totais | Até três envios totais, conforme política existente de GPU ocupada | Registra persistência do erro e segue |
| Diagnóstico Colab indisponível: transporte, 408/409/429/5xx | Não se aplica | Registra falha antes do envio de geração | O próximo par confere a conexão novamente |
| HTTP 401/403 ou cota OpenAI esgotada | Não repete | Autenticação/permissão não são repetidas | Interrompe novas chamadas e consolida os dados disponíveis |
| Outra rejeição HTTP de geração, como 400/422 | Não repete | Não repete | Registra falha do par e permite os seguintes |
| Resposta sem escolha válida/incompatível com protocolo | Não aplica geração | Não aplica geração | Registra falha operacional do par |
| Recusa, JSON de correção inválido ou resposta não aplicável | Usa o resultado do avaliador de resposta/aplicação | Preserva também o estado de geração | São respostas recebidas, distintas de ausência de resposta por transporte |
| Mudança de identidade Colab ou configuração incompatível | Contrato confere configuração | Manifesto e modelo continuam conferidos | Interrompe novas chamadas |
| Orçamento atingido ou parada solicitada | Interrompe novos envios | Interrompe novos envios | Finaliza sessão e tenta consolidar |

No OpenAI, o SDK permanece com `max_retries=0`: somente o laço explícito faz
retentativas, evitando multiplicação entre duas camadas. O backoff é exponencial;
`Retry-After` numérico é respeitado até 60 segundos. O timeout configurado do SDK é
120 segundos. No Colab, a espera por 429 continua limitada a 30 segundos e o timeout
de geração continua configurável por `COLAB_TIMEOUT_S`.

A classificação segue os tipos/status da API descritos na
[documentação oficial de erros](https://developers.openai.com/api/docs/guides/error-codes)
e no [SDK Python](https://developers.openai.com/api/reference/python). O Colab mantém
uma política própria para evitar duplicar uma geração longa após perder a conexão.

Cada envio OpenAI passa pelo limite `MAX_LLM_CALLS`, inclusive retentativas e falhas.
O custo confirmado é reconciliado separadamente. Após timeout ou erro sem uso confirmado,
o custo não é inventado: pode haver processamento remoto que o cliente não observou.
`MAX_USD` protege o custo conhecido, não garante um teto exato sobre cobranças desconhecidas.
As reservas persistentes Colab continuam ativas.

## Registro e interpretação das métricas

- `llm_operacional.jsonl`: categoria, caso, estratégia, fatalidade, status HTTP, horários,
  duração e envios conhecidos. Eventos novos são gravados com flush e fsync durante a fila.
- Respostas OpenAI recebidas: número de envios, histórico de erros recuperados e indicação
  de consumo incerto são preservados no artefato e na tentativa.
- `metricas.json`: seção `operacional_llm`, com categorias, estratégias, eventos, retentativas
  com resposta, pares afetados e limites de completude do custo.
- `eventos_llm.csv`: eventos operacionais, quando presentes.
- `finalizacao.json`: códigos de saída distintos do pipeline e da consolidação, produzido
  tanto pelo terminal quanto pelo painel.

Uma chamada sem resposta não cria tentativa científica fictícia nem atribui R/F/M=0.
As taxas por tentativa usam as respostas efetivamente registradas. O denominador de
CR por caso mantém todos os casos solicitados. Casos incompletos continuam pendentes;
o relatório fica `consolidado_parcial`. Ausência de observações deixa taxas por tentativa
indisponíveis, sem fabricar uma taxa de sucesso ou de falha.

Sessões sem resposta possuem JSONL vazio nas novas execuções. O leitor também aceita
recuperação histórica sem esse arquivo quando há sessão e falha operacional verificáveis.
Eventos históricos não ganham contagem de envios, tokens ou custos presumidos.
As fontes são validadas e identificadas por hashes durante a consolidação.

O código de saída continua não zero quando a campanha tem erros, mesmo que as métricas
tenham sido publicadas. O painel mantém a indicação de falha/interrupção e registra o
código da consolidação separadamente. Uma retomada compatível pode refazer pares sem
resposta, respeitando a parada da cadeia na primeira correção aceita.

## Validação e recuperação do piloto histórico

Os testes unitários usam HTTP sintético e processos locais controlados, sem API real,
GPU ou testes funcionais do alvo. Cobrem cache desligado com entrada corrompida,
retentativas, orçamento por envio, continuidade entre prompts/casos, autenticação,
sessão vazia, recuperação histórica, consolidação após erro e o caminho do painel.

Resultado final: **387 testes aprovados**. O preflight
`AMP_PREFLIGHT_20261103T001314Z_6d294aea` concluiu os **78 casos com K=4**, cache de
respostas desligado, zero tentativas e nenhuma chamada à API; pipeline e consolidação
terminaram com código zero. O identificador usa UTC; a validação ocorreu em 02/11
no horário local. O [resumo de validação](../../../../outputs/resiliencia_llm/VALIDACAO_20261102/resumo.json)
registra hashes do código e das evidências; o log unitário está na mesma pasta.

```bash
.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -q
```

Foi recuperado o piloto `AMP_REAL_20261017T222912Z_abd18103`, interrompido por HTTP 503.
As métricas foram publicadas em uma pasta nova, sem modificar seus arquivos originais:
[relatório recuperado](../../../../outputs/resiliencia_llm/RECUPERACAO_PILOTO_20261102_METRICAS/metricas.json).
O resultado informa zero tentativas científicas concluídas e um caso pendente. A chamada
histórica falhou; recuperar o relatório não significa executar ou corrigir o caso.

Para repetir a consolidação offline, escolha outro destino inédito:

```bash
.venv/bin/python scripts/relatorios/consolidar_metricas.py \
  --execucao AMP_REAL_20261017T222912Z_abd18103 \
  --entrada outputs/piloto_colab_1_issue/AMP_REAL_20261017T222912Z_abd18103 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/resiliencia_llm/NOVA_RECUPERACAO_METRICAS \
  --definicao-f criterio
```

Não foi iniciada campanha real para validar esta feature. Falta de energia, encerramento
forçado do sistema, disco cheio e evidência corrompida podem impedir a finalização; esta
implementação não transforma essas condições em sucesso nem sobrescreve evidências.
