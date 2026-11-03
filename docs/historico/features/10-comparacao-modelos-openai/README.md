# Feature 10 — Escolha dos modelos para a comparação experimental

**Data da decisão:** 02/11/2026.  
**Status:** justificativa preservada e seleção dos modelos implementada; campanhas reais pendentes. Veja a [entrega](ENTREGA.md).  
**Modelos selecionados:** `gpt-4.1-mini`, `gpt-5.6-luna` e `gpt-6-luna`.  
**Escopo da decisão original:** somente documentação. A implementação foi autorizada posteriormente e está registrada separadamente na entrega.

As mudanças no seletor do frontend, no recebimento pelo backend e no histórico
estão detalhadas em [Alterações no frontend e integração com o backend](ENTREGA.md#alterações-no-frontend-e-integração-com-o-backend).

## 1. Objetivo

Comparar três modelos da OpenAI na geração de correções para os mesmos 78 casos
identificados pelo SAST no Juice Shop. A avaliação observará remoção do alerta,
preservação funcional, introdução de novos alertas, custo e tempo de execução,
mantendo os critérios R/F/M e as estratégias P1–P4 do projeto.

A escolha combina a referência já utilizada, GPT-4.1 mini, com duas famílias mais
recentes voltadas a tarefas de baixo custo, GPT-5.6 Luna e GPT-6 Luna. O interesse
é investigar se modelos mais recentes apresentam resultados melhores neste conjunto
de casos e qual o custo de obter uma correção aceita.

Essa é uma hipótese experimental. A numeração dos modelos, a posição comercial e
o preço não demonstram antecipadamente qual deles corrigirá mais casos.

## 2. Contexto da decisão sobre o Colab

Matheus e Caio decidiram retirar o Colab da próxima comparação após dificuldades
com o acesso ao servidor de inferência pelo computador local via ngrok e com o
retorno das requisições. Os notebooks, diagnósticos e registros permanecem no
repositório para documentar a tentativa e suas limitações operacionais.

O piloto `AMP_REAL_20261017T222912Z_abd18103` possui registro de HTTP 503 e teve suas
métricas recuperadas offline na [feature 09](../09-resiliencia-llm/README.md).
Esse episódio documenta uma falha de execução. Não permite concluir sobre a qualidade
das correções que o Qwen produziria em uma infraestrutura funcional.

Usar a API OpenAI nos três tratamentos reduz diferenças de infraestrutura de
hospedagem entre eles. Essa escolha não elimina falhas de API, diferenças de limites
de acesso ou mudanças do serviço, que continuam precisando de registro.

## 3. Justificativa dos três modelos

| Modelo | Papel no experimento | Justificativa da seleção |
|---|---|---|
| `gpt-4.1-mini` | Referência do projeto | Já foi utilizado nas campanhas e possui registros reais de custo, tokens e resultados. Mantê-lo permite relacionar a nova avaliação ao histórico, com as diferenças de protocolo explicitadas. |
| `gpt-5.6-luna` | Tratamento de geração intermediária | Introduz uma família mais recente que a referência e anterior à família GPT-6, com proposta de uso econômico. Permite investigar mudanças de resultados e custo nessa transição. |
| `gpt-6-luna` | Tratamento mais recente do trio | Acrescenta outra geração à comparação, mantendo uma opção orientada a tarefas delimitadas e volume elevado. Permite verificar se essa evolução oferece vantagem no cenário de correção avaliado. |

As descrições e os preços foram consultados na documentação oficial da OpenAI:
[GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) e
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).

Mini e Luna são categorias comerciais distintas. A seleção não pressupõe igualdade
de arquitetura, tamanho, dados de treinamento ou capacidade. A comparação avalia
os modelos e configurações disponíveis como tratamentos completos; não isola o
efeito causal de uma mudança de arquitetura ou de geração.

## 4. Geração sem etapa de raciocínio configurada

A comparação proposta não terá um tratamento adicional com raciocínio ativado.
Para os dois Luna, a configuração pretendida é `reasoning_effort="none"` em
Chat Completions, conforme o suporte descrito nas páginas oficiais dos modelos.
Essa configuração deverá ser validada na integração antes das campanhas.

Os Luna pertencem a famílias que oferecem raciocínio configurável. Escolher o modo
`none` significa desativar essa etapa na requisição; não significa reclassificar
essas famílias como modelos que não possuem capacidade de raciocínio. Também não
comprova equivalência dos mecanismos internos entre os três modelos.

O modo solicitado e os demais parâmetros efetivos precisarão constar nos contratos
e registros. Asserções sobre ausência de consumo de tokens de raciocínio dependerão
dos dados de uso que a API efetivamente disponibilizar, sem inventar valores ausentes.

Não será solicitado texto adicional de cadeia de pensamento. O formato de saída
continuará sendo o JSON de correção previsto no projeto, incluindo seus campos de
justificativa. As estratégias P1–P4 serão preservadas.

## 5. Condições necessárias para uma comparação válida

Os três modelos deverão usar o mesmo catálogo de 78 ocorrências, o mesmo commit
do alvo, perfil SAST, critérios R/F/M, conjunto D, revisão funcional e baseline
compatível. A preparação dos 78 casos está documentada na
[feature 08](../08-ampliacao-cobertura-78/README.md).

Também deverão ser preservados:

- Conteúdo dos prompts, contexto fornecido e base RAG, sem ajustes específicos para
  favorecer um modelo depois de observar seus resultados.
- Cache local de respostas desligado, com `LLM_CACHE=desligado`.
- Limites de saída, timeout e retentativas definidos antes da campanha, considerando
  a compatibilidade dos parâmetros com cada modelo.
- Ambiente funcional, política de seleção dos testes e tratamento de falhas da API.
- Registro do modelo solicitado e retornado, versão/snapshot quando disponível,
  parâmetros, tokens, custo, duração e identificadores de infraestrutura disponíveis.
- Saídas próprias para cada modelo e rodada, sem sobrescrever campanhas anteriores.

O uso de parâmetros com o mesmo nome não garante comportamento equivalente entre
modelos. Em particular, compatibilidade de `seed`, `temperature`, formato estruturado
e limites de geração precisará ser conferida; não basta trocar `OPENAI_MODEL`.

A regra atual de encerrar a cadeia de um caso na primeira correção aceita será
mantida, salvo uma futura alteração explícita do desenho experimental. Dessa forma,
os modelos podem alcançar quantidades diferentes de chamadas. Estratégias posteriores
recebem populações condicionadas às falhas anteriores; suas taxas isoladas não
demonstram um efeito causal do prompt.

A campanha histórica com 52 casos e uso de cache permanece como histórico. Para
uma comparação principal com os novos modelos, o GPT-4.1 mini deverá ter uma nova
rodada nas mesmas condições dos 78 casos, se seu acesso ainda estiver disponível.

## 6. Definição de rodada e estimativa de custo

Uma rodada completa corresponde a executar o pipeline para **78 casos com P1–P4
em um único modelo**. São até **312 chamadas primárias** antes das retentativas.
Uma rodada em cada um dos três modelos representa até **936 chamadas primárias**.
A parada na primeira correção aceita pode reduzir esses totais.

Os preços Standard consultados, em dólares por um milhão de tokens, foram:

| Modelo | Entrada sem desconto de cache | Saída |
|---|---:|---:|
| [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) | US$ 0,40 | US$ 1,60 |
| [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) | US$ 0,20 | US$ 1,20 |
| [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) | US$ 0,10 | US$ 0,50 |

Para a projeção de entrada, foram usados os 312 prompts do
[preflight dos 78 casos](../../../../outputs/campanha_docker/AMP_PREFLIGHT_20261103T001314Z_6d294aea/prompts/)
e os [registros da campanha histórica](../../../../outputs/campanha_docker/AMP_PAINEL_20261019T183425Z_282e13b4/resultados_consolidados/execucoes.jsonl).
Foi possível associar 193 prompts a mensagens idênticas já observadas; os outros
119 foram estimados por uma relação linear entre caracteres e tokens de entrada
do histórico. O total projetado foi de aproximadamente **611.735 tokens de entrada**.
Não é uma tokenização exata nem garante a mesma contagem nos novos modelos.

As chamadas históricas sem cache tiveram média de aproximadamente 549 tokens de
saída. O cenário A arredonda essa referência para 600 por chamada. O cenário B
supõe que todas as 312 respostas consumam 4.096 tokens de saída, limite atual do cliente.

| Modelo | Cenário A: 600 tokens de saída/chamada | Cenário B: 4.096 tokens de saída/chamada |
|---|---:|---:|
| GPT-4.1 mini | US$ 0,54 | US$ 2,29 |
| GPT-5.6 Luna | US$ 0,35 | US$ 1,66 |
| GPT-6 Luna | US$ 0,15 | US$ 0,70 |
| Total de uma rodada em cada modelo | Aproximadamente US$ 1,05 | Aproximadamente US$ 4,65 |

Os totais são arredondados a partir dos valores calculados antes do arredondamento
individual. A fórmula utilizada é:

```text
custo = (tokens_entrada × preço_entrada + tokens_saida × preço_saida) / 1.000.000
```

Esses números são simulações, não gastos realizados ou valores exatos garantidos.
Excluem retentativas, impostos, câmbio, diferenças de cobrança de cache do provedor
e custo do computador. O cenário B não é um teto financeiro: reenvios, alteração
do limite de saída e outras diferenças de consumo podem elevar o custo.

As médias de saída do GPT-4.1 mini não devem ser atribuídas aos Luna como se já
tivessem sido medidas. Um piloto comum aos três modelos deverá produzir dados
reais para atualizar o orçamento antes da campanha completa. Se forem adotadas
repetições, o orçamento deverá incluir cada rodada adicional.

## 7. Resultados que deverão orientar a análise

A análise deverá apresentar correções aceitas pelos critérios R/F/M, preservação
funcional, alertas remanescentes e novos, custo por correção aceita e duração.
Essas medidas serão apresentadas por modelo e com os estratos disponíveis no
catálogo, sem tratar as 78 ocorrências como vulnerabilidades já confirmadas.

Falhas da API, respostas inválidas e resultados de aplicação/validação continuarão
distinguíveis. Ausência de resposta por transporte não criará uma tentativa científica
fictícia nem será convertida em R/F/M=0. Casos pendentes e completude dos dados deverão
acompanhar as taxas, conforme a política da feature 09.

O estudo terá alcance de três modelos da OpenAI neste alvo e desenho experimental.
Não sustentará conclusões gerais sobre todos os fornecedores ou toda correção de
vulnerabilidades. Recência, custo menor ou resultado agregado melhor também não
garantem superioridade em todas as regras e casos.

## 8. Disponibilidade e implementação futura

A OpenAI anunciou a retirada do GPT-4.1 mini da API para **14/01/2027**. A execução
da referência deverá considerar essa data e o acesso efetivo da conta.
[Fonte oficial: descontinuações](https://developers.openai.com/api/docs/deprecations).
Não deverá haver substituição silenciosa do modelo se ele deixar de estar disponível.

Antes da campanha, será necessário implementar e validar perfis de parâmetros,
preços e identificação dos modelos; conferir geração estruturada sem raciocínio
ativado; preparar configurações e saídas separadas; e executar um piloto com o
mesmo subconjunto de casos para os três tratamentos.

A seleção, os perfis e os testes offline estão descritos na [entrega de implementação](ENTREGA.md).
Permanecem pendentes o piloto com API real, a confirmação de acesso da conta e as
campanhas completas. A justificativa e as estimativas desta decisão não são resultados
medidos nos Luna. O `.env` pessoal, os notebooks e as campanhas históricas foram preservados.
