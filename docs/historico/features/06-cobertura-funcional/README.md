# Feature 06 — Cobertura funcional dos 78 casos

**Status:** implementada e validada; 52 casos preparados e 26 bloqueados. Campanha completa pendente. Veja [a entrega](ENTREGA.md).  
**Data:** 17/10/2026.  
**Dependências:** features 01–05, política de validação relacionada e comparador SAST v2.  
**Objetivo:** revisar a cobertura funcional por ocorrência e por arquivo, preparar seleções de testes justificadas e executáveis e explicitar onde ainda não é possível medir F com cobertura suficiente.

## 1. Problema e estado inicial verificado

O catálogo contém 78 ocorrências em 46 arquivos. O mapa atual lista todos esses
arquivos, mas somente `routes/login.ts` e `routes/keyServer.ts` possuem
`modo: relacionados`, abrangendo dois casos. Os outros 44 arquivos, com 76 casos,
estão em `modo: amplo`. Essa classificação é um fallback operacional; não é uma
revisão da adequação dos testes.

Há 13 casos em 11 arquivos de frontend, incluindo três ocorrências em dois
arquivos `.spec.ts`. A compilação T0 atual executa `tsc --noEmit` na raiz, cujo
`tsconfig.json` exclui `frontend`. O seletor atual aceita somente testes do
servidor e de API. Portanto, aprovar T0 ou testes de servidor não comprova
compilação ou comportamento Angular.

O projeto possui testes de frontend com o builder `@angular/build:unit-test`,
configurado em `frontend/angular.json`. Sua execução seletiva, preparação e
relatórios ainda precisam ser verificados. Não presumir Karma, navegador ou
comando de filtragem sem conferir a configuração e a versão instaladas.

Veja o [inventário inicial dos 46 arquivos](INVENTARIO_INICIAL.md). Ele registra
contagens e a seleção atual, sem atribuir adequação funcional aos testes.

Fontes locais de autoridade:

- [Catálogo ampliado](../../../../outputs/catalogos/ampliado_v1/catalogo_issues.json).
- [Mapa atual](../../../../config/mapa_testes_relacionados.yaml).
- [Seletor](../../../../src/pipeline/etapas/e07_validacao/selecao.py) e [runner](../../../../src/pipeline/etapas/e07_validacao/camadas.py).
- [Política relacionada](../../../validacao_relacionada.md).
- [Protocolo](../../../protocolo_experimental.md) e [comparador v2](../../../auditoria/comparador_v2.md).

## 2. Escopo e limites

Entregar:

1. Inventário reconciliado dos 78 casos e 46 arquivos, com funcionalidades e domínios.
2. Revisão dos testes existentes, incluindo suas asserções, preparação e alcance.
3. Matriz por caso com adequação, evidências e lacunas.
4. Novo mapa versionado contendo apenas associações efetivamente revisadas.
5. Lista priorizada de testes adicionais e execução das seleções cuja cobertura for declarada validada.
6. Proteções para que F positivo dependa do domínio e dos testes efetivamente executados.
7. Relatório de entrega com cobertura alcançada e pendências para a campanha.

Não exigir um teste novo para cada alerta. Casos que compartilham comportamento
podem compartilhar testes, com justificativa individual. Também não considerar
que todos os alertas de um arquivo têm a mesma cobertura: `server.ts` concentra
12 casos e `lib/insecurity.ts`, seis, envolvendo mecanismos distintos.

Preservar catálogo, inclusões de falsos positivos/inconclusivos, prompts, RAG,
regras, comparador, definição das três separações F/D e parada da cadeia. Não
usar soluções de codefixes como testes funcionais nem enviar testes de avaliação
novos aos prompts/RAG. Não executar campanha, LLM, commit ou push nesta feature.

Preparar cobertura não significa obrigatoriamente eliminar todas as lacunas.
O aceite da auditoria e a prontidão para executar os 78 casos são estados distintos.

## 3. Inventário e revisão por comportamento

Criar `scripts/audit/audit_functional_coverage.py`, inicialmente somente por leitura.
Receber catálogo, checkout, mapa, arquivo de revisão e saída nova por argumentos.
Usar caminhos confinados à raiz declarada, biblioteca padrão e PyYAML. Não
executar testes, instalar dependências ou chamar serviços ao importar ou auditar.

Reconciliar os casos por `caso_id` e os arquivos por caminho normalizado, sem
deduplicar ocorrências. Validar commit, hashes do catálogo, ausência de IDs
desconhecidos/duplicados, fontes ausentes e caminhos externos/symlinks de escape.
Contagens 78/46 são o aceite deste catálogo, não constantes genéricas do programa.

Para cada ocorrência, revisar:

- Função, endpoint, componente, template, configuração ou comportamento envolvido.
- Entradas, resultado esperado e dependências compartilhadas relevantes.
- Testes candidatos e asserções que sustentam a associação; nomes semelhantes não bastam.
- Caminhos normais e erros relevantes ao comportamento, sem exigir exploração do alerta para definir F.
- Preparação de dados, hooks, serviços, timeouts e possibilidade de execução isolada.
- Testes de desafios presentes na seleção e classificação vigente de F/D.
- Lacunas e testes adicionais necessários, com prioridade e justificativa.

Revisar também configurações, templates e dados estáticos: não inventar uma API
para arquivos como `Gruntfile.js`, `users.yml` e `promotionVideo.pug`. Um teste de
configuração só serve como evidência do comportamento que realmente verifica.

## 4. Contrato da matriz de cobertura

Manter a revisão autoral em `config/cobertura_funcional_v1.yaml`, com schema
versionado, commit alvo e hashes do catálogo. O relatório gerado terá uma linha
por caso e agregação por arquivo, preservando valores ausentes.

Campos mínimos por caso:

| Campo | Contrato |
|---|---|
| `caso_id`, `arquivo`, `check_id` | Identidade igual à do catálogo |
| `funcionalidade`, `dominio` | Descrição concreta; domínio servidor, frontend, configuração/dados, template ou teste |
| `comportamentos_esperados` | Comportamentos e asserções necessários para o alcance declarado |
| `testes` | Caminho, origem, grupo de execução e asserções relevantes |
| `compilacao_necessaria` | Alvos aplicáveis; explicitar quando o T0 da raiz é insuficiente |
| `revisao` | `pendente`, `adequada` ou `insuficiente`, com justificativa e evidência de código |
| `execucao_baseline` | `nao_executada`, `comparavel`, `bloqueada_ambiente` ou `inconclusiva`, com referência ao relatório |
| `elegivel_f_positivo` | Derivado da revisão, capacidade do runner e evidências exigidas; nunca preenchido por mera existência do teste |
| `lacunas`, `testes_adicionais` | Listas explícitas, inclusive vazias; não substituir por uma aprovação implícita |
| `limitacoes` | O que a seleção não observa, incluindo efeitos em outros componentes |

Revisão adequada não significa que o patch futuro passou. Baseline comparável
não exige zero falhas: exige identificar falhas anteriores e aplicar a política
vigente. Relatórios devem apresentar separadamente revisão, capacidade do runner,
execução no baseline e resultado após patch.

## 5. Critérios de adequação e interpretação de F

Uma associação pode ser considerada adequada quando as asserções exercitam o
comportamento declarado, a preparação é reproduzível e o conjunto cobre as
dependências relevantes identificadas na revisão. Cobertura de linhas é auxiliar,
não substitui a revisão de asserções e não será exigido um percentual arbitrário.

Para F positivo após um patch:

1. Todos os arquivos alterados devem ser considerados, inclusive arquivos adicionais ao caso.
2. Executar a união dos testes necessários, sem duplicação e sem seleção vazia.
3. Executar compilação/verificações dos domínios aplicáveis.
4. Conferir nos relatórios que os testes esperados foram executados, sem seleção totalmente ignorada, falha de carregamento ou relatório ausente.
5. Comparar com baseline compatível e aplicar as definições F/D e repetição vigentes.
6. Registrar o escopo efetivamente observado, sem atribuir aprovação a etapas não executadas.

Lacuna de cobertura, domínio sem suporte, timeout ou seleção não comprovada não
autorizam F=1. Quando a execução funcional for inconclusiva, manter `null` e
`indeterminada_funcional`; uma falha funcional já comprovada pode permanecer
F=0. Casos recusados antes da LLM são pendências de preparação, não tentativas
de correção nem falhas da LLM.

Na política relacionada, não acionar automaticamente a suíte inteira para
contornar uma lacuna. Manter a decisão atual de executar testes da funcionalidade.
Bibliotecas compartilhadas podem exigir vários grupos relacionados, com alcance
explícito; quando não for possível delimitá-los, registrar insuficiência.

R/M continuam sendo medidos pelo SAST global independentemente de F. Testes
funcionais não substituem confirmação de segurança, e desaparecimento de alerta
não confirma preservação funcional.

## 6. Frontend e integridade da avaliação

Inventariar os testes Angular existentes e revisar quais componentes, serviços,
guards e templates eles realmente exercitam. Registrar separadamente compilação
do frontend, testes unitários de componentes e testes de integração/navegação.
Um teste de componente não comprova automaticamente o fluxo completo no navegador.

Fazer uma prova técnica de execução seletiva sem modo watch, usando o runner
real do checkout. Registrar comando, versão, dependências, testes selecionados,
resultados e limitações. Se viável, implementar um adaptador que preserve setup,
baseline, isolamento e relatório verificável. Se isso não for demonstrado, manter
os casos afetados bloqueados para F positivo e documentar o adaptador como pendência.

Não inserir testes frontend nas listas `unitarios`/`api` atuais: elas aceitam
apenas os caminhos de servidor/API. Qualquer extensão exige schema explícito,
leitura compatível do mapa antigo e suporte real no seletor/runner.

Três ocorrências do catálogo estão em arquivos de teste `.spec.ts`. Um patch
nesses arquivos não pode obter F=1 apenas removendo testes ou enfraquecendo as
próprias asserções usadas como avaliação. Preservar evidências de avaliação
independentes, conferir hashes/seleção e marcar insuficiência quando a alteração
comprometer o avaliador. Esses casos permanecem no catálogo.

Testes adicionais de avaliação devem ser versionados neste repositório, sob
`tests/functional/juice_shop/`, com instalação/staging reproduzível e hashes.
Não escrever silenciosamente testes no commit congelado do Juice Shop nem alterar
o checkout da feature 01. Manter essas verificações fora de `make test-unit`.

## 7. Publicação, integração e rastreabilidade

Publicar um novo mapa em `config/mapa_testes_relacionados_v2.yaml`, preservando o
arquivo v1. O sufixo é a revisão do artefato; se novos domínios exigirem alteração
de estrutura, declarar também a nova versão de schema. Não ativar o novo mapa
automaticamente no YAML padrão antes das verificações da entrega.

O preflight deverá apresentar por caso: associação revisada, suporte do runner,
domínios necessários e lacunas. Na política relacionada, recusar os casos sem
preparação suficiente antes de criar o cliente LLM. Reavaliar a cobertura após
conhecer todos os arquivos do patch; aprovação do preflight não garante F positivo.

Incluir no contrato e nas identidades do cache os hashes do mapa, revisão de
cobertura, testes adicionais e adaptadores relevantes. Mudanças exigem outra
execução/saída; não migrar resultados nem reutilizar evidências incompatíveis.
Preservar leitura e interpretação de contratos/resultados históricos.

Registros, métricas e painel devem distinguir domínio, testes selecionados,
executados/ignorados, baseline, cobertura suficiente/insuficiente e limitações.
Não agrupar aprovações somente de servidor e aprovações de frontend como se
observassem o mesmo alcance. Não alterar os denominadores científicos existentes.

## 8. Saídas e execução da validação

O auditor publicará, em destino novo sob `outputs/cobertura_funcional/`:

- `cobertura_por_caso.json` e `.csv`: exatamente 78 linhas de casos.
- `cobertura_por_arquivo.json` e `.csv`: exatamente 46 arquivos.
- `lacunas.json` e `plano_testes_adicionais.md`: pendências priorizadas, sem inventar evidência.
- `resumo.json`: contagens por domínio, revisão, capacidade de execução e prontidão.
- `manifesto.json`: entradas e hashes, commit, schemas e artefatos gerados.

Usar UTF-8, ordenação estável, JSON/CSV determinísticos e cabeçalhos em grupos
vazios. Recusar destino existente, sobreposição com entradas e escrita concorrente;
publicar com lock exclusivo, temporário irmão e revalidação das entradas. CLI:
`0` sucesso, `2` argumentos inválidos e `1` falhas de dados/execução. `--help`
e auditoria por leitura devem funcionar fora da raiz, sem LLM ou serviços.

Executar testes reais por comando separado da auditoria. Preparar checkout de
validação limpo no commit fixado, sem restaurar alterações desconhecidas. Registrar
dependências efetivas e gerar baseline funcional novo, sem sobrescrever
`outputs/baseline_testes.json` ou os baselines das features anteriores.

Cada seleção declarada validada deve ter execução demonstrada no baseline; testes
compartilhados podem usar uma evidência compatível, sem simular 78 execuções
independentes. Registrar falhas preexistentes, repetições, duração e limites.
Quando houver testes adicionais, incluir controles de regressão deliberada em
fixtures isoladas para demonstrar que suas asserções detectam o comportamento
quebrado. Não usar remoção de alerta como oráculo funcional.

## 9. Ordem de implementação

1. Capturar hashes das entradas e gerar o inventário, sem executar o alvo.
2. Revisar login/keyServer e as dependências compartilhadas; não presumir adequação dos dois mapeamentos atuais.
3. Revisar demais rotas, servidor, bibliotecas, configuração/dados e template.
4. Revisar os 13 casos frontend e executar a prova técnica do runner nativo.
5. Priorizar e adicionar testes que resolvam lacunas comprovadas; registrar o restante.
6. Publicar mapa/revisão novos e integrar proteções de cobertura, contratos e registros.
7. Validar seleções, controles, determinismo e preservação histórica.
8. Produzir `ENTREGA.md` nesta pasta e atualizar protocolo, guia e índice com evidências.

Priorizar lacunas que afetam vários casos, componentes compartilhados e seleções
que hoje produziriam uma aprovação com alcance incorreto. Registrar o ganho por
casos preparados, sem classificar falsos positivos ou inconclusivos como descartáveis.

## 10. Testes e critérios de aceite

### Testes automatizados do pipeline

- [x] Reconciliação por ocorrência, contagens, IDs e hash/commit divergentes.
- [x] YAML duplicado, caminhos externos, symlinks, fontes/testes ausentes e revisões inconsistentes.
- [x] Vários casos no mesmo arquivo com necessidades distintas e união de arquivos alterados.
- [x] Seleção vazia, testes ignorados, relatório ausente e falha operacional impedindo F positivo.
- [x] T0 do servidor insuficiente para frontend; domínio/adaptador não suportado explicitamente bloqueado.
- [x] Alteração de testes avaliadores sem aprovação por remoção de asserções.
- [x] Separação F/D, falhas do baseline, indeterminação funcional e SAST independente de F.
- [x] Contratos/cache incompatíveis recusados e leitura dos resultados históricos preservada.
- [x] Publicação determinística, sem sobrescrita, concorrência, alteração de entradas e CLI fora da raiz.
- [x] Testes unitários sem LLM, Semgrep, instalação ou testes funcionais do alvo.

### Aceite da entrega

- [x] 78 casos e 46 arquivos reconciliados, sem alteração do catálogo.
- [x] Os 78 casos têm revisão concluída (`adequada` ou `insuficiente`); pendências de testes/ambiente possuem motivo e plano, sem aprovação implícita.
- [x] Adequação distinguida de simples mapeamento e de execução bem-sucedida.
- [x] Todo caso declarado preparado tem revisão adequada, suporte real do runner e evidência de baseline comparável.
- [x] Frontend, arquivos de teste e componentes compartilhados têm limitações explícitas.
- [x] Lacunas impedem F positivo; resultados indicam o alcance realmente executado.
- [x] Novo mapa e baselines preservam os anteriores; nenhuma alteração automática da configuração padrão.
- [x] Seleções declaradas validadas e controles de regressão possuem evidências executáveis.
- [x] `make test-unit`, hashes históricos, limpeza do alvo e `git diff --check` conferidos.
- [x] Relatório inclui comandos, ambiente, hashes, contagens, tempos, testes adicionais e pendências.

**Aceite para iniciar a campanha dos 78:** somente quando os 78 casos estiverem
preparados segundo os critérios acima. Caso a auditoria termine com lacunas,
declarar a campanha completa pendente e listar os casos já aptos para um piloto.
Não reduzir o catálogo para tornar artificialmente completa a cobertura.


## 11. Decisões da implementação

A revisão versionada contém 39 grupos únicos de execução, com testes existentes
e três grupos adicionais. O mapa usa schema 2.0 e deriva integralmente da revisão.
A política `relacionada_v2` é optativa e exige contrato 4.0 e baseline 2.0.

Servidor usa o T0 da raiz; Angular possui compilação própria development/AOT e
Vitest/jsdom, com timeout de 300 segundos e repetição integral de grupo. Testes
unitários Node desta política terminam naturalmente: o controle de ambiente
registrou enumeração incompleta com `--test-force-exit`. APIs mantêm o isolamento
anterior e conferência de identidades contra baseline.

O novo conjunto D conserva 75 entradas e não acrescenta mocks Angular a D sem
evidência que satisfaça os critérios vigentes. Lacunas de CAPTCHA aritmético, ZIP,
campanha e legendas permanecem explícitas mesmo com testes próximos passando.
Veja os [comandos operacionais](../../../cobertura_funcional.md).
