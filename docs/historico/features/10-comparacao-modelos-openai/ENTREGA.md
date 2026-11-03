# Entrega — Seleção dos três modelos OpenAI no pipeline

**Data:** 02/11/2026.  
**Escopo:** GPT-4.1 mini, GPT-5.6 Luna e GPT-6 Luna selecionáveis por terminal, YAML e painel.  
**Validação:** offline, com SDK real sobre HTTP sintético, testes do painel e preflight sem inferência.

## Comportamento implementado

`executar.py --modelo` permite escolher `gpt-4.1-mini`, `gpt-5.6-luna` ou
`gpt-6-luna` sem editar o `.env`. O YAML aceita o campo opcional `modelo`, e o
painel possui o seletor **Modelo para a próxima execução**. O Make aceita `MODELO`.

A prioridade é a seleção no comando/painel, depois o campo do YAML, depois o
provedor e modelo configurados no ambiente. Uma seleção explícita de um dos três
modelos força OpenAI, inclusive quando o `.env` ainda aponta para Colab. Sem seleção
explícita, as configurações anteriores continuam disponíveis.

O seletor fica bloqueado durante a execução. Atualizações da tela não apagam a
escolha do usuário. O histórico identifica o modelo do contrato; trocar a seleção
para a próxima rodada não altera o processo atual ou os arquivos de configuração.

`config/execucao_docker_78.yaml` define `modelo: gpt-4.1-mini` como padrão, mantendo
os 78 casos, P1–P4, K=4, revisão funcional e baseline. O padrão histórico de 52 casos
do Makefile continua separado; para os 78, informe essa configuração explicitamente.

## Alterações no frontend e integração com o backend

O painel recebeu o campo **Modelo para a próxima execução**, junto ao modo de
execução e ao botão **Iniciar pipeline**. O seletor apresenta:

- **Usar configuração atual:** mantém o modelo/provedor definidos pela configuração.
- **GPT-4.1 mini:** referência já utilizada no projeto.
- **GPT-5.6 Luna — sem raciocínio:** envia o perfil com `reasoning_effort=none`.
- **GPT-6 Luna — sem raciocínio:** envia o mesmo ajuste de raciocínio desativado.

Ao iniciar, o frontend envia o identificador selecionado no corpo do pedido
`POST /api/iniciar`, juntamente com o modo. O servidor valida a seleção, o controle
do painel repassa `--modelo` ao orquestrador e o cliente usa o perfil correspondente.
Uma seleção explícita OpenAI prevalece sobre um `.env` ainda configurado para Colab.

O modelo do YAML preenche inicialmente o seletor quando disponível. A escolha feita
pelo usuário permanece durante o polling da tela. O campo fica desabilitado enquanto
há uma execução ativa; mudar a seleção para uma rodada posterior não modifica uma
execução já iniciada. A opção de configuração atual não acrescenta uma substituição
de modelo ao pedido.

O histórico passou a exibir o modelo do contrato ao lado do identificador da execução.
Assim, o modelo associado a um resultado anterior é identificado independentemente
da opção escolhida para a próxima rodada.

| Arquivo | Alteração |
|---|---|
| [index.html](../../../../src/pipeline/painel/web/index.html) | Campo de seleção de modelo nos controles do painel. |
| [app.js](../../../../src/pipeline/painel/web/app.js) | Preenchimento das opções, preservação da escolha, bloqueio durante execução, envio do modelo e identificação no histórico. |
| [servidor.py](../../../../src/pipeline/painel/servidor.py) | Recebimento do campo `modelo` e opção inicial `--modelo` ao iniciar o painel. |
| [controle.py](../../../../src/pipeline/painel/controle.py) | Validação do modelo, repasse ao processo, armazenamento no estado e exposição das opções ao frontend. |
| [painel_modelos.test.cjs](../../../../tests/integration/painel_modelos.test.cjs) | Teste do HTML e JavaScript reais com jsdom: seleção, polling, bloqueio e corpo do POST. |
| [test_painel.py](../../../../tests/unit/test_painel.py) | Testes do recebimento HTTP e do repasse ao processo, incluindo recusa de modelo inválido. |

Para usar a interface atualizada, reinicie o servidor do painel e recarregue a
página. Confira os casos e estratégias apresentados, escolha o modo e o modelo
e clique em **Iniciar pipeline**. Os comandos para abrir o painel com os 78 casos
estão na seção de execução abaixo.

## Perfis de geração e custo

| Parâmetro | GPT-4.1 mini | GPT-5.6 Luna / GPT-6 Luna |
|---|---|---|
| API | Chat Completions | Chat Completions |
| Saída | JSON Schema estrito da correção | Mesmo JSON Schema |
| Temperatura | 0 | 0 |
| Seed | `OPENAI_SEED`, padrão 42 | Não enviada; registro de seed fica nulo |
| Raciocínio | Parâmetro não enviado | `reasoning_effort: "none"` explícito |
| Limite de geração | 4.096 tokens | 4.096 tokens |
| Timeout e retentativas | 120 s por requisição; até três envios para erros transitórios | Mesma política |

Os parâmetros compatíveis foram conferidos nas páginas de
[GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) e no
[guia da família](https://developers.openai.com/api/docs/guides/latest-model).
A configuração `none` foi verificada nos payloads sintéticos; nenhuma geração real
foi feita para demonstrar comportamento do servidor ou acesso da conta.

A tabela `config/precos_llm.yaml` inclui os três modelos. O cálculo considera tokens
de entrada normais, leitura de cache do provedor, escrita de cache padrão de 30 minutos
e saída, sem contar duas vezes os tokens escritos. Nos Luna, aplica as tarifas de
contexto longo quando a entrada excede 272 mil tokens. As regras de cobrança são
documentadas no [guia de cache do provedor](https://developers.openai.com/api/docs/guides/prompt-caching).

O cache local de respostas permanece desligado por padrão e é independente do cache
de processamento do provedor. Quando explicitamente ativado para replay, sua chave
considera modelo, parâmetros efetivos, schema e hash da tabela de preços. Uma alteração
de preços durante a sessão impede novos envios pelo cliente já criado.

Os limites `MAX_LLM_CALLS` e `MAX_USD` continuam acumulados entre rodadas e modelos.
Trocar o modelo não reinicia o orçamento. Para planejar várias rodadas, considere
o consumo já registrado e os possíveis reenvios; o limite de chamadas pode encerrar
a sessão antes do processamento de todos os casos. Valores de custo desconhecidos
continuam explicitamente identificados.

## Terminal, YAML e Docker

Na raiz do repositório, em ambiente preparado:

```bash
python executar.py --config config/execucao_docker_78.yaml \
  --modelo gpt-6-luna --modo preflight
```

Troque o valor de `--modelo` por qualquer um dos três modelos. Para conferir os
comandos sem executar a preparação, acrescente `--mostrar-comando`.

Para uma execução com inferência, use `--modo real`. Esse modo usa a chave OpenAI
e consome os limites acumulados; não foi executado nesta entrega.

O YAML também pode definir o modelo:

```yaml
modelo: gpt-5.6-luna
```

No Docker, a imagem já usada pelo baseline da revisão funcional v6 é:

```bash
export TCC_DOCKER_IMAGE=sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_docker_78.yaml --modelo gpt-6-luna --modo preflight
```

Para abrir o painel com os mesmos 78 casos:

```bash
docker compose run --rm --service-ports tcc .venv/bin/python painel.py \
  --endereco 0.0.0.0 --config config/execucao_docker_78.yaml --modelo gpt-6-luna
```

O acesso continua em `http://127.0.0.1:8765`. Escolha o modelo antes de iniciar.

Os atalhos também aceitam a seleção:

```bash
make docker-preflight CONFIG=config/execucao_docker_78.yaml MODELO=gpt-5.6-luna
make docker-painel CONFIG=config/execucao_docker_78.yaml MODELO=gpt-6-luna
```

Os atalhos Make mantêm a verificação da referência histórica em `docker/referencia.json`.
Nesta máquina, sua imagem `sha256:81fe6403f07a05ccf7a911211e54ff2ae44c6b12237768b0a84ec1c7167ff5be`
não estava instalada; `make docker-check` informou essa ausência. A referência não
foi substituída. A validação desta entrega usa os comandos diretos e a imagem da
revisão v6 acima, identificada separadamente da referência histórica.

## Contratos, registros e métricas

A identidade de inferência guarda modelo solicitado, parâmetros efetivos, SDK,
tabela de preços e hashes das implementações. Uma retomada com outro modelo ou
configuração é recusada pelo contrato; cada modelo deve ter sua própria execução.

As respostas e tentativas registram modelo solicitado e retornado, parâmetros,
tokens de raciocínio quando informados e tokens de leitura/escrita de cache do
provedor. Campo ausente não é convertido automaticamente em zero tokens de raciocínio.
Uma resposta de outra família/modelo é recusada antes de aplicar alterações.
Snapshots datados da família solicitada são reconhecidos; uma requisição a snapshot
específico exige o mesmo snapshot na resposta.

As colunas adicionais aparecem em `tentativas.csv`, e a agregação existente
`metricas_por_inferencia.csv` distingue as identidades. O leitor verifica os campos
novos contra o contrato sem exigir sua presença em registros históricos anteriores
à feature. Respostas truncadas ou recusadas não produzem edição, mesmo quando seu
texto pode ser interpretado como JSON.

## Verificações e limites

Foram aprovados **405 testes unitários no host e no Docker**, incluindo os testes
existentes de orçamento, recuperação de erros e Colab. Os novos cenários verificam:

- Payloads do SDK dos três modelos, omissão de seed nos Luna e raciocínio configurado como `none`.
- Seleção por CLI/YAML/painel, prioridade sobre ambiente Colab e recusa de modelos desconhecidos.
- Tarifas dos três modelos, cache do provedor, contagens inconsistentes e mudança de preços.
- Resposta do SDK até leitura verificável e publicação CSV, recusando troca de modelo no registro.
- Contrato recusando raciocínio ativado ou seed inventada no perfil Luna.

O teste DOM do seletor pode ser reproduzido na imagem com as dependências frontend
da worktree preparadas:

```bash
docker compose run --rm --no-deps tcc node --test tests/integration/painel_modelos.test.cjs
```

Esse teste usa jsdom e transporte simulado, sem abrir navegador ou chamar a API.
Foi aprovado: **um teste DOM, zero falhas**.

Também concluíram o preflight com **78 casos, 312 prompts e K=4** em cada execução:

| Modelo | Execução |
|---|---|
| GPT-4.1 mini | `AMP_PREFLIGHT_20261103T013702Z_c0fb5065` |
| GPT-5.6 Luna | `AMP_PREFLIGHT_20261103T013924Z_198229e0` |
| GPT-6 Luna | `AMP_PREFLIGHT_20261103T014113Z_81a9085f` |

Os 312 pares caso/estratégia têm os mesmos hashes de prompt nas três execuções.
Cada uma publicou suas métricas, com códigos zero no pipeline e na consolidação,
zero tentativas de correção e nenhum custo de API. Os identificadores usam UTC;
as verificações ocorreram em 02/11 no horário local.

O [resumo de validação](../../../../outputs/feature10/SELECAO_MODELOS_20261102/resumo.json)
contém IDs, parâmetros, preços, hashes das entradas e evidências. Os logs unitários,
do DOM e dos preflights estão na mesma pasta. Os resultados completos e métricas
estão sob `outputs/campanha_docker/`, nas pastas desses IDs e respectivas irmãs `_METRICAS`.

Os preflights verificam preparação e proveniência; não demonstram acesso aos modelos
pela conta ou qualidade de correção. O piloto real e as campanhas permanecem pendentes.

Não foram alterados prompts, RAG, critérios R/F/M, catálogo, testes funcionais do alvo,
notebooks ou campanhas históricas. O `.env` pessoal foi preservado.
