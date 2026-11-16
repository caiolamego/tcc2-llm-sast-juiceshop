# Execução real de duas issues — 14/10/2026

Execução autorizada pelo usuário para os casos de `routes/login.ts` e `routes/keyServer.ts`. Seleção por conveniência operacional, já utilizada no dry-run; não é amostra representativa do catálogo. Modelo solicitado: gpt-4.1-mini; seed 42; K=1; P1/P2/P3/P4; sem P1L. Credencial somente no `.env` local, ignorado pelo Git; nenhum valor de chave integra este relatório.

## Preparação

Um perfil novo foi gerado a partir do YAML sanitizado e das regras locais, sem consultar regras remotas. Caminho: `../../config/perfis/ampliado_piloto_v1/perfil.json`. Sua identidade é o hash registrado no contrato. Ele possui bytes/hashes diferentes do perfil histórico, cuja descrição foi preservada. O preflight reproduziu exatamente os 78 alertas e montou oito prompts dos dois casos. A checagem funcional da worktree limpa passou usando a referência da feature 02.

## Resultado

Foram registradas **8 tentativas reais**, sem cache e sem erros de execução. Custo estimado pelo pipeline: **US$ 0.010012**. Modelo retornado: gpt-4.1-mini-2025-04-14. A worktree foi restaurada e ficou limpa; os patches não foram aplicados permanentemente ao alvo.

- **login.ts:** P1/P2/P3/P4 tiveram R=1, F_criterio=1 e M=1, com classificação `aceita`. Nas definições sem separação e marcador, F=0. Cinco testes de ataques SQL falharam após os patches e foram classificados como D em `criterio`; isso exige leitura contextual e não significa que toda a suíte passou sem separação.
- **keyServer.ts:** as quatro estratégias aplicaram patches e passaram em F. R e M permaneceram nulos por ambiguidade de pareamento no mesmo grupo regra/arquivo, sem erro operacional ou novo diagnóstico de parsing afetando o alvo. Nenhuma tentativa recebeu aceite automático.

## Diferença entre parada e classificação

O código atual usa `classificacao_sem_separacao` para encerrar a cadeia, embora `classificacao_final` use `criterio`. Por isso login continuou após o aceite de P1 pela definição principal. Esse comportamento não foi alterado durante o experimento.

A consolidação da feature 04 delimita sua população principal pela primeira classificação original `aceita`: neste caso usa cinco tentativas (quatro keyServer + login P1) e identifica login P2/P3/P4 como pós-aceite relativo a esse recorte. Todas as oito tentativas permanecem no CSV e no custo total. A execução física realizou oito tentativas; o recorte das métricas não deve ser confundido com uma cadeia que efetivamente parou em P1.

Antes da avaliação final, alinhar explicitamente a definição de parada, a classificação principal e o recorte da análise. Os registros deste piloto devem ser preservados sem reclassificação silenciosa. O orçamento acumulado local consumiu 8/8 chamadas; futuras chamadas exigem revisar o limite, sem apagar o histórico de custos.

## Evidências

- [Resumo estruturado](RESUMO_EXECUCAO.json).
- [Registro das oito tentativas](AMP_PILOTO_2_REAL_20261014/resultados_consolidados/execucoes.jsonl).
- [Sessão](AMP_PILOTO_2_REAL_20261014/resultados_consolidados/AMP_PILOTO_2_REAL_20261014_sessoes.json).
- [Métricas](AMP_PILOTO_2_REAL_20261014_METRICAS/metricas.json).
- [CSV de todas as tentativas](AMP_PILOTO_2_REAL_20261014_METRICAS/tentativas.csv).
- [Preflight](AMP_PILOTO_2_PREFLIGHT_20261014/preflight.json).
- [Log de execução](AMP_PILOTO_2_REAL_20261014.console.log).

Os diretórios de execução também contêm prompts, respostas, patches, scans, comparações e testes. Nenhum commit ou push foi realizado nesta execução.
