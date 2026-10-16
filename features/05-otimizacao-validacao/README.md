# Feature 05 — Otimização da validação e do tempo de execução

**Status:** implementação e matriz de replay verificadas; veja resultados e limites em [ENTREGA.md](ENTREGA.md).  
**Data:** 16/10/2026.  
**Dependências:** features 01–04, piloto real de duas issues e lançador/painel local.  
**Objetivo:** reduzir trabalho repetido por tentativa e avaliar K=2, preservando a interpretação de R/F/M e a rastreabilidade do experimento com 78 casos.

## 1. Problema e referência

No piloto `AMP_PILOTO_2_REAL_20261014`, foram registradas oito tentativas:

| Etapa | Tempo observado por tentativa |
|---|---:|
| Geração pela LLM | 3,18–5,30 s |
| SAST global | 20,88–21,97 s |
| T0 — verificação TypeScript | 3,14–3,43 s |
| T2 — unitário relacionado de keyServer | 0,16–0,18 s |
| T3 — unitários do servidor | 3,09–3,32 s |
| T4 — API de keyServer | 30,77–32,87 s |
| T4 — API de login, incluindo repetição | 61,43–62,81 s |

Esses tempos são evidências do piloto, não metas garantidas para os 78 casos. Login
não teve T2 selecionado pelo mapeamento atual por nome. Não concluir que uma seleção
de API relacionada terá custo equivalente ao unitário de keyServer.

Fontes locais de autoridade:

- [Runner atual](../../src/pipeline/validation/runner.py).
- [Orquestrador](../../src/pipeline/run_pipeline.py).
- [Contrato ampliado](../../src/pipeline/execucao_ampliada.py).
- [Resumo do piloto](../../outputs/piloto_2_issues/RESUMO_EXECUCAO.json).
- [Protocolo experimental](../../docs/protocolo_experimental.md).
- [Plano de validação desta feature](VALIDACAO.md).

## 2. Entregas e limites

Implementar cinco frentes:

1. Cache verificável de evidências para estados de código idênticos.
2. Seleção explícita de testes unitários e de API relacionados.
3. Triagem funcional antes da validação ampla.
4. Benchmark de execução sequencial e com duas worktrees.
5. Investigação da repetição somente dos testes de API que falharam.

Preservar catálogo, classificação da auditoria, prompts, RAG, regras e comparação
SAST global. Preservar a política vigente de F/D, baseline e tratamento de falhas
intermitentes; otimizar sua execução não autoriza redefinir esses conceitos.

Não executar as 78 issues, instalar dependências ou chamar a LLM como consequência
da simples criação desta especificação. A implementação será seguida pelos testes
descritos em `VALIDACAO.md`; uma nova rodada real será uma execução separada.

Não alterar resultados antigos, limpar caches anteriores, modificar limites do
`.env`, apagar worktrees existentes, fazer commit ou push automático.

## 3. Fluxo proposto e proteção das métricas

Manter `historica_v1` como política de referência, com ordem e resultados atuais.
Adicionar `otimizada_v1` inicialmente opcional:

```text
Aplicar patch e identificar todos os arquivos alterados
                    ↓
Conferir identidade do estado e procurar evidências compatíveis
                    ↓
T0 + unitários relacionados + API relacionada (triagem funcional)
                    ↓
SAST global e comparação por ocorrência
                    ↓
T3 + T4 amplos, quando a triagem não tiver comprovado reprovação funcional
                    ↓
Registrar evidências, cobertura, tempos, cache e R/F/M
```

“Aprovado na triagem” refere-se à triagem **funcional**, aplicando a mesma separação
F/D do runner. Uma falha exclusivamente de D não é automaticamente reprovação de
`F_criterio`; as demais etapas continuam para obter os três resultados de F.

Regras obrigatórias:

- Se uma etapa comprovar `F_criterio=0`, as definições mais estritas também ficam
  reprovadas, conforme o contrato vigente. É possível dispensar as suítes restantes
  e registrar os motivos, sem declará-las executadas.
- Uma aprovação apenas nos testes relacionados ainda não autoriza F final positivo:
  quando a triagem passa, executar as suítes amplas exigidas pelo perfil.
- Após um patch aplicável, medir SAST global mesmo quando a triagem reprovar. Isso
  mantém R/M observáveis independentemente de F, como no fluxo atual.
- `R=0`, `M=0` ou R/M indeterminados não dispensam uma medição funcional ainda
  necessária. Evitar introduzir ausência seletiva de F nas métricas.
- Patch não aplicado, falha operacional ou ausência de evidência seguem os estados
  existentes; não transformar uma etapa não executada em sucesso ou duração zero.
- Compilação, testes relacionados e suítes amplas devem usar as mesmas regras de
  baseline, repetição e classificação F/D.

Os candidatos que passam por todas as etapas podem não ficar mais rápidos. A
triagem pode acrescentar custo, especialmente se iniciar a API duas vezes. O
benchmark deve medir esse custo e permitir desabilitar uma seleção sem ganho.

### Interfaces implementadas

As opções públicas são `--politica-validacao`, `--mapa-testes`, `--cache-validacao`
e `--repeticao-api`, também opcionais no YAML. Os padrões permanecem
`historica_v1`, cache desligado e repetição ampla. O arquivo anterior continua válido.
Novas execuções ampliadas usam contrato 3.0; leitores preservam 1.0/2.0, mas uma
retomada incompatível não é migrada nem sobrescrita. O preflight continua possível
sem dependências do alvo. A política otimizada exige mapa e catálogo ampliado.

`config/execucao_otimizada.exemplo.yaml` é uma configuração separada, em modo
preflight. Não altera os limites do `.env` nem o K da configuração original.

## 4. Cache de evidências de validação

Separar cache de validação do cache de respostas LLM. Usar diretório local próprio,
por exemplo `.cache/validacao/v1/`, com publicação atômica, lock por chave e sem
sobrescrever uma entrada válida. Dois workers não devem executar a mesma medição
simultaneamente quando puderem compartilhar uma entrada já em produção.

### 4.1 Identidade

Derivar a chave de serialização canônica contendo, no mínimo:

- Commit original, identidade do baseline SAST e baseline funcional.
- Estado efetivo dos arquivos do alvo: caminhos, tipos, conteúdos e exclusões
  relevantes, incluindo criações/remoções. Confirmar que nenhuma alteração externa
  ficou fora da identidade; bytes do diff isoladamente não bastam.
- Perfil SAST, regras, flags e versão efetiva do Semgrep.
- Política e implementação da validação, mapa de testes e seleção efetiva.
- Classificação F/D, configuração de repetição, timeouts e demais módulos que
  influenciem os resultados, não somente o arquivo `runner.py`.
- Versões efetivas do Node e demais ferramentas usadas, lockfile e proveniência
  verificada da instalação das dependências. Sem identidade confiável de ambiente,
  recusar o compartilhamento da evidência.
- Variáveis operacionais relevantes, como TZ, sem armazenar credenciais.

Não usar apenas `caso_id`, estratégia, nome de arquivo, contagem de linhas ou hash do
prompt. Não incluir segredos, timestamps ou caminho absoluto da worktree na chave.

### 4.2 O que pode ser reutilizado

- Scan global pós-patch e seus diagnósticos, quando a identidade SAST for igual.
- Evidências funcionais completas ou uma reprovação de triagem reproduzível, quando
  a identidade funcional e a cobertura exigida forem iguais.
- Separar identidades SAST/funcional se a implementação fizer cache por componente.

**R/M devem ser recalculados para a ocorrência atual.** Duas issues podem produzir
o mesmo estado de código e compartilhar um scan, mas têm alvos diferentes para R.
Reexecutar o comparador com a identidade da ocorrência e as fontes apropriadas.

Preservar um registro por tentativa/estratégia. Materializar e conferir os artefatos
na execução consumidora, com hashes e referência à origem; não criar dependência
frágil de um diretório temporário ou de symlink externo.

Recusar entradas adulteradas, incompletas, de política incompatível ou com cobertura
insuficiente. Não reutilizar timeout, falha técnica, relatório inválido ou conjunto
com falhas intermitentes. Uma entrada invalidada deve ser medida novamente.

Reutilizar observações não transforma tentativas em réplicas independentes. Os
relatórios devem permitir identificar quantas medições efetivas foram executadas.

## 5. Mapa explícito de testes relacionados

Criar `config/mapa_testes_relacionados.yaml` com schema versionado. Para cada arquivo
ou padrão de origem, declarar:

- Arquivos de testes unitários e de API, sem comandos shell arbitrários.
- Justificativa da associação e cobertura conhecida.
- Dependências compartilhadas e necessidade de fallback amplo.
- Ausência de teste relacionado, quando comprovada; não confundir com ausência de
  funcionalidade afetada ou com aprovação.

Validar caminhos relativos internos, existência, tipos, duplicatas e padrões. Selecionar
a união dos testes de **todos os arquivos alterados**, não somente o arquivo do alerta.
Uma mudança em biblioteca compartilhada, dependência, configuração ou helper de
testes deve acionar fallback conservador para as suítes potencialmente afetadas.

Arquivos desconhecidos ou cobertura insuficiente acionam o fallback amplo. Não
inventar associação pelo nome nem interpretar seleção vazia como testes aprovados.
O mapeamento por nome atual pode auxiliar na autoria, mas não substitui a revisão.

Começar por `routes/login.ts` e `routes/keyServer.ts`, examinando os testes existentes
e suas dependências. Inventariar a cobertura dos 78 casos; lacunas não bloqueiam a
execução quando o fallback amplo estiver explicitamente registrado.

Na implementação v1, as entradas do mapa são caminhos literais. Não há descoberta
automática por grafo de dependências nem seleção por severidade ou auditoria. Os
46 arquivos foram inventariados; dois têm associação específica e 44 permanecem
com fallback amplo. Isso não declara cobertura funcional de frontend.

Se a triagem já executar uma suíte ampla como fallback, não a executar novamente no
mesmo estado. Reutilizar a evidência dentro da própria tentativa, com sua cobertura.
Manter os testes escolhidos iguais entre estratégias para o mesmo conjunto alterado.

## 6. Repetição seletiva de T4

Manter a repetição ampla como padrão inicial. Oferecer a política seletiva apenas
depois de comprovar equivalência no subconjunto de validação.

Na política candidata, após novas falhas na primeira execução ampla de API:

1. Extrair identidades estáveis do JUnit, distinguindo arquivo, suíte e teste.
2. Resolver os arquivos e filtros suportados pela versão efetiva do Node, escapando
   metacaracteres e preservando hooks, fixtures e preparação necessários.
3. Executar a seleção em processo novo e confirmar no relatório quais testes foram
   efetivamente executados. Zero testes ou testes apenas ignorados não comprovam sucesso.
4. Aplicar a mesma interseção de falhas novas e classificação F/D da política atual.
5. Fazer fallback para repetição ampla quando houver timeout, falha de carga,
   identidade ambígua, seleção incompleta ou dependência de ordem/estado não resolvida.

Uma execução isolada pode ocultar uma falha que só ocorre com a suíte inteira.
Comparar repetição seletiva e ampla nos patches arquivados e em fixtures que
simulem dependência de ordem. Se houver divergência ou evidência insuficiente,
entregar a investigação e manter a política ampla habilitada. Não forçar a otimização
para cumprir uma meta de tempo.

## 7. Duas worktrees e recursos compartilhados

Preparar `wt-2` no mesmo commit de `wt-1`, com instalação pelo lockfile e versões
efetivas registradas. Conferir limpeza e dependências antes do benchmark; não
restaurar alterações desconhecidas nem alterar `workspace/catalogo-alvo/`.

K controla casos concorrentes; P1–P4 permanecem sequenciais dentro de cada caso,
respeitando a regra de parada existente. Manter o lock de T4 e estendê-lo à seleção
relacionada/repetição de API quando usar os mesmos recursos conflitantes.

Medir separadamente espera por worktree, espera pelo lock de API, execução e tempo
de parede da sessão. Não somar duração de workers como tempo de parede. Registrar
uso de memória e eventuais timeouts/conflitos. K=2 só vira configuração recomendada
se houver benefício observado sem perda de estabilidade.

Não alterar automaticamente K no `execucao.yaml`. Garantir que lançador e painel
mostrem o K efetivo e continuem impedindo duas execuções concorrentes pelo painel.

## 8. Integração, registros e métricas

Criar componentes efetivos de seleção, cache e política sob `src/pipeline/validation/`.
Manter as interfaces públicas legadas e a opção de fluxo histórico. Integrar as
opções no orquestrador, lançador, painel, sondagem e tentativa individual; não deixar
um consumidor usando política diferente sem registro.

Adicionar seleção explícita, por exemplo `--politica-validacao historica_v1|otimizada_v1`,
`--mapa-testes` e `--cache-validacao desligado|leitura|leitura-escrita`. O schema de
`config/execucao.yaml` deve aceitar os novos campos opcionais e continuar aceitando
o arquivo anterior. A repetição seletiva terá chave própria, ampla por padrão.

Versionar o contrato novo, usando `schema_versao=3.0`, com suporte explícito nos
loaders e relatórios. Incluir política, mapa, classificação F/D, implementação,
ambiente e configuração de repetição/cache. Fixar a política antes da campanha.
Preservar leitura de 1.0/2.0 e as identidades dos artefatos antigos. Retomadas não
podem trocar política, mapa ou código relevante; não adicionar campos retroativamente.
K pode variar apenas sob a regra de retomada já existente e com registro operacional.

Registrar por tentativa:

- Política, mapa/hash, testes selecionados e executados, cobertura e fallback.
- Etapas `executada`, `reutilizada`, `dispensada_por_reprovacao` ou `nao_aplicavel`,
  com motivo; cobertura parcial nunca equivale a aprovação final.
- Cache de validação por componente: chave, origem, hashes, motivo de hit/miss e
  evidência original. Manter separado de `do_cache`, que se refere à resposta LLM.
- Tempos realmente gastos agora: LLM, preparação, seleção, lookup, SAST, testes,
  comparação, esperas, restauração e total, definindo as fronteiras de cada medição.
- Tempos originais da evidência reutilizada em campos separados. Não atribuir esse
  tempo novamente ao trabalho atual nem apresentar economia estimada como medição.
- Classificações R/F/M e as três definições de F, sem mudar a regra de parada vigente.

Atualizar o painel para distinguir cache LLM/cache de validação, etapas dispensadas,
tempo atual e tempo original. Atualizar métricas para preservar denominadores,
separar falhas técnicas e não tratar reutilização como nova cobrança ou nova réplica.

## 9. Testes e critérios de aceite

### Implementação

- [x] Seleção por múltiplos arquivos, mapas inválidos, caminhos externos, seleção
  vazia, dependências compartilhadas e fallback amplo cobertos por testes.
- [x] Cache verifica conteúdo, ambiente, políticas, hashes e publicação concorrente;
  invalida entradas corrompidas e alterações ocorridas durante a medição/publicação.
- [x] Duas ocorrências no mesmo estado compartilham scan, mas têm R recalculado.
- [x] Reuso não apaga registros por estratégia nem depende de artefatos temporários.
- [x] Triagem preserva F/D, R/M e estados de ausência; testes reprovados dispensam
  apenas trabalho comprovadamente desnecessário.
- [x] Repetição seletiva detecta seleção incompleta, colisões de nomes, hooks,
  dependência de ordem e necessidade de fallback.
- [x] K=2, lock de API, cancelamento seguro, restauração e espera de cache testados
  com processos sintéticos; nenhuma worktree real usada pelos testes unitários.
- [x] Contratos antigos, contrato novo, retomada incompatível, métricas e painel
  cobertos sem chamadas à LLM, Semgrep ou API de rede nos testes unitários.

### Validação posterior

- [x] Testes unitários e checks existentes passando; falhas anteriores registradas.
- [x] Benchmark em saídas novas usando os oito patches arquivados, conforme
  [VALIDACAO.md](VALIDACAO.md), sem chamadas à LLM.
- [x] Concordância de R/M e das três definições de F entre referência e otimizado;
  divergências investigadas, sem descartar silenciosamente resultados inconvenientes.
- [x] Cache frio/quente, K=1/K=2 e repetição ampla/seletiva identificados separadamente.
- [x] Tempos, cobertura, picos de recursos e limites documentados; nenhuma promessa
  de ganho baseada apenas na remoção de etapas ou na execução de zero testes.
- [x] Perfil recomendado escolhido pelas evidências. Repetição ampla e K=1 podem
  permanecer recomendados se as opções alternativas não se mostrarem adequadas.
- [x] Saídas históricas, catálogo, prompts, regras e checkout de referência preservados;
  worktrees limpas e `git diff --check` aprovado.
- [x] `ENTREGA.md`, protocolo, README, guia e comandos atualizados somente com
  verificações concluídas; condições ainda pendentes claramente identificadas.

Não declarar redução de tempo sem benchmark. O aceite não exige um percentual
arbitrário de aceleração; exige medição, evidência íntegra e preservação dos resultados.
Se o fluxo otimizado for mais lento ou divergir, mantê-lo experimental e preservar
a política histórica como padrão.
