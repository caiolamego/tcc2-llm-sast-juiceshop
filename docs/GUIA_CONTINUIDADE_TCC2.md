# Guia de continuidade do TCC2 — diagnóstico, checklists e plano de execução

**Data da análise:** 12/10/2026.  
**Projeto:** correção de vulnerabilidades com LLM, SAST e testes no OWASP Juice Shop.  
**Autores:** Matheus de Siqueira Brant e Caio Magalhães Lamego.  
**Orientadora:** Profa. Dra. Elaine Venson.  
**Branch examinada:** `semgrep-findings`, após integração da `main`, considerando também as alterações locais de reorganização ainda sem commit.

> **Situação atual — 13/10/2026:** o catálogo ampliado de 78 casos já foi integrado, e P1/P2/P3/P4 geraram 312 prompts no preflight sem API. O próximo trabalho é preparar o piloto de correções reais e delimitar a cobertura funcional/dinâmica, especialmente frontend. Os diagnósticos iniciais abaixo preservam o contexto anterior às features 01–03.

Este documento é um diagnóstico e um plano de trabalho. Checkboxes marcadas representam implementações ou evidências encontradas; não significam que o ambiente foi reproduzido integralmente nesta máquina. Atualize os itens com links para as evidências de conclusão.


> **Atualização — feature 01 concluída:** o [catálogo ampliado](../outputs/catalogos/ampliado_v1/catalogo_issues.json) foi gerado e validado com 78 casos por ocorrência e 46 exclusões. Veja a [entrega](../features/01-catalogo-ampliado/ENTREGA.md). Nessa etapa, o pipeline ainda consumia os 12 casos históricos e a integração estava pendente. O diagnóstico abaixo preserva o estado inicial da análise, e os checklists foram atualizados apenas nos itens comprovados.


> **Atualização — feature 02 concluída:** seleção de catálogo/perfil/saída, reprodução dos 78 casos, comparação por ocorrência e contrato de retomada foram implementados. O preflight real gerou 156 prompts P1/P2. O dry-run de dois casos percorreu as etapas; uma simulação teve F=0 por teste dependente de número de linha. Veja a [entrega](../features/02-integracao-catalogo/ENTREGA.md). O modo histórico permanece como padrão. Essa entrega antecedeu RAG; a validação específica de frontend segue pendente.

> **Atualização — feature 03 concluída:** dez documentos e manifesto 1.0 publicados; recuperação por CWE/categoria/fallback; P3/P4 completos; 115 testes e preflight real com 312 prompts. P1/P2/P1L e 559 artefatos históricos preservados. O contrato 2.0 protege a base; compatibilidade antiga comprovada em cópia temporária. Veja a [entrega](../features/03-rag-prompts/ENTREGA.md). Nenhuma correção real foi executada nesta feature.

> **Atualização — feature 04 concluída:** calculador reutilizável, consolidação JSON/CSV, denominadores explícitos e separação de simulação/diagnóstico implementados. 153 testes passaram; dry-run e preflight foram consolidados e reproduzidos. RRIS real e pesos opcionais continuam sem entradas. A divergência preexistente do perfil remoto foi registrada e um snapshot exato recuperado. Veja a [entrega](../features/04-metricas-consolidacao/ENTREGA.md). Próximo passo: piloto real, selecionando um perfil íntegro.

## 1. Documentos que orientam o trabalho

| Fonte | Como utilizar |
|---|---|
| [TCC1](../../TCC1___Caio_Lamego_e_Matheus_Brant-11.pdf) | Compromissos acadêmicos, perguntas de pesquisa, estratégias, métricas e limitações. Ver especialmente §§1.3 e 3.5–3.12. |
| [Guia de arranque original](<../../GUIA ARRANQUE TCC2.pdf>) | Fases F0–F8 e critérios operacionais. Seus comandos e algumas decisões antecedem a implementação atual. |
| [Protocolo experimental](protocolo_experimental.md) | Decisões registradas sobre alvo, filtragem, SAST, parâmetros e validação. Precisa incorporar a expansão. |
| [Caderno de laboratório](caderno_de_laboratorio.md) | Problemas encontrados, decisões e observações anteriores. |
| [Estrutura atual](estrutura_projeto.md) | Localização dos componentes após reorganização. |
| [Auditoria inicial](auditoria/auditoria_cobertura_semgrep.md) e [rodada 12](auditoria/auditoria_rodada12.md) | Evolução da cobertura, evidências e limites. |
| [Relatório do scan combinado](../outputs/auditoria_sast/combinado-hZGD7r/RELATORIO.md) | Contagens consolidadas e classificação de escopo. |
| [Inventário de integração](../tests/integration/README.md) | Testes disponíveis por rodada e lacunas de validação dinâmica. |

**Ordem de interpretação:** o TCC1 define a proposta; o código e os artefatos mostram o que foi feito; decisões posteriores devem ser registradas no protocolo. Este guia não transforma recomendações em resultados nem substitui o alinhamento metodológico com a orientadora.

## 2. Compromisso do TCC1 e decisões atuais

O objetivo é avaliar um fluxo que integra SAST, LLM e testes para remover alertas, preservar funcionalidade e não introduzir novas issues. O trabalho inclui quatro estratégias:

| Estratégia | Composição planejada | Estado |
|---|---|---|
| P1 | Código associado ao alerta e instrução simples | Implementada e executada |
| P2 | P1 e roteiro de análise em etapas | Implementada e executada |
| P3 | Código, diagnóstico SAST e contexto documental recuperado | Implementada; preflight sem API validado |
| P4 | P3 e roteiro de análise em etapas | Implementada; preflight sem API validado |
| P1L | P1 com localização e identificação explícita do alerta | Diagnóstico adicional implementado; não substitui P3/P4 |

Um template é reutilizado para vários casos; cada tentativa recebe um prompt montado com seus dados. Não é necessário escrever manualmente um prompt exclusivo para cada issue. P1/P2 podem gerar mensagens iguais para alertas no mesmo arquivo, pois não incluem o diagnóstico explícito.

### Decisões já estabelecidas na conversa

- [x] Usar o Juice Shop como alvo e a PoC Python como referência histórica.
- [x] Tentar corrigir os alertas dentro do escopo **mesmo quando classificados como falsos positivos ou inconclusivos**.
- [x] Excluir os alertas fora do escopo documentado.
- [x] Manter a classificação da auditoria para análise, sem usá-la como exclusão por veracidade.
- [x] Organizar regras por rodada e scripts por finalidade.
- [x] Remover as entradas antigas de compatibilidade da raiz de `scripts/` e adotar os comandos novos.
- [x] Padronizar o inventário de testes por rodada, identificando explicitamente integrações ausentes.
- [ ] Registrar formalmente a política do novo conjunto no protocolo e alinhar as alterações metodológicas com a orientadora.

**Distinção necessária:** excluir por escopo não é excluir falso positivo. O TCC1 §3.12 já previa não eliminar previamente possíveis falsos positivos. Nesses casos, o resultado deve ser descrito como remoção de alerta; não como prova de correção de uma vulnerabilidade real.

## 3. O que existe hoje

### 3.1 Três conjuntos que não devem ser confundidos

| Conjunto | Conteúdo | Uso atual |
|---|---|---|
| Catálogo histórico | 15 ocorrências brutas, 12 casos após deduplicação por regra/arquivo | Entrada atual do pipeline; base de E01/E02 |
| Seleção exploratória anterior | 16 grupos de correção associados a 20 desafios | Proposta intermediária que seleciona somente confirmados; não atende à decisão atual |
| Auditoria ampliada | 124 alertas brutos; 78 dentro do escopo; 50 desafios associados confirmados | Fonte para construir o novo catálogo; ainda não integrada ao pipeline |

No scan combinado:

| Classificação | Quantidade | Tratamento decidido para o novo conjunto |
|---|---:|---|
| Confirmados | 55 | Incluir |
| Falsos positivos | 21 | Incluir |
| Inconclusivos | 2 | Incluir |
| Fora do escopo | 46 | Excluir com justificativa |
| **Total dentro do escopo** | **78** | **Base antes de definir a unidade e deduplicação** |

Os 46 fora do escopo são 31 em `data/static/codefixes/`, 13 em `.github/`, um em `.npmrc` e um em `frontend/.npmrc`. Correspondem a soluções de referência e configurações de CI/CD ou de dependências, excluídas pelo recorte do experimento.

**Alerta, desafio e caso de correção são unidades diferentes.** Um patch pode afetar vários desafios; regras distintas podem apontar para a mesma causa. O número final de casos ainda precisa ser definido e justificado. Se houver agrupamento, todo alerta incluído deve continuar rastreável a algum caso.

O scan combinado registra 50 avisos de parsing, sendo 20 erros de sintaxe e 30 casos de parsing parcial. A contagem de achados não implica cobertura completa do alvo. As regras locais foram desenvolvidas após inspeção do projeto: apresentar essa expansão como exploratória, sem atribuir a ela uma medição independente de recall.

### 3.2 Execuções de correção já registradas

| Execução | Tentativas registradas | Estratégias | Reuso de cache |
|---|---:|---|---:|
| E01 | 24 | P1/P2 sobre os 12 casos históricos | 5 |
| E02 | 36 | P1/P2 e diagnóstico P1L sobre os 12 casos históricos | 24 |

Em E02, a cadeia P1/P2 reconstruída sob a definição `criterio` considera 21 tentativas, 3 aceitas e 3 casos aceitos em 12: TRV por tentativa de 14,29% e proporção de casos aceitos de 25%. Os casos são JS005, JS006 e JS011; JS005/JS006 apontam para o mesmo trecho sob regras diferentes. Esses números não representam o novo catálogo.

Fonte: [métricas E02](../outputs/resultados_consolidados/E02_metricas.json). A seleção da definição de F altera os números; E01 contém classificações retrospectivas incompletas. E01/E02 não são repetições independentes de geração: parte das respostas foi reutilizada do cache.

### 3.3 Ambiente e evidências locais

- [x] Código do orquestrador, cliente LLM, aplicação de patches e pool de worktrees disponível.
- [x] Baselines, respostas, diffs e registros consolidados históricos disponíveis.
- [x] Regras e fixtures organizadas em `rules/rodada1/` até `rules/rodada12/`.
- [x] Na última validação da reorganização: 51 testes Python passaram; 28 testes Semgrep passaram na etapa anterior; seis `.mjs` passaram pela verificação de sintaxe.
- [ ] Reproduzir o ambiente completo em um único ambiente Python documentado.
- [ ] Preparar `.env` e `workspace/`: ausentes nesta cópia durante a análise.
- [ ] Executar as integrações reorganizadas: verificação de sintaxe não equivale à execução.
- [ ] Recuperar artefatos de E01/E02 que não vieram para esta cópia.
- [ ] Revisar e versionar a reorganização: ainda há arquivos movidos, alterados e não rastreados.

Foram encontradas **115 referências a artefatos ausentes dentre 230 referências** em `artefatos` das 60 tentativas. Essa contagem é por referência e não por arquivo único. Não significa que os arquivos estejam perdidos na máquina de origem. O `.gitignore` ignora prompts, testes, SAST posterior e códigos corrigidos; essa política precisa ser resolvida antes da coleta final.

## 4. Mapa dos arquivos e responsabilidades

| Local | Responsabilidade e atenção necessária |
|---|---|
| [run_pipeline.py](../src/pipeline/run_pipeline.py) | Orquestra casos, estratégias, validações e retomada; modo histórico padrão, ampliado por seleção explícita. |
| [prompts/builder.py](../src/pipeline/prompts/builder.py) | Monta P1/P2/P3/P4/P1L. RAG exige base completa e manifesto consistente. |
| [llm/openai_client.py](../src/pipeline/llm/openai_client.py) | API, cache, custos e orçamento. |
| [llm/schema.py](../src/pipeline/llm/schema.py) | Estrutura esperada da correção. |
| [patching/applier.py](../src/pipeline/patching/applier.py) | Valida e aplica edições por âncora. |
| [target/workspace.py](../src/pipeline/target/workspace.py) | Pool de worktrees e restauração entre tentativas. |
| [sast/semgrep_client.py](../src/pipeline/sast/semgrep_client.py) | Execução e normalização SAST; rulesets antigos e assinatura por regra/arquivo. |
| [sast/filtro.py](../src/pipeline/sast/filtro.py) | Filtros antigos de categoria, severidade e CWE, também utilizados em M. |
| [validation/runner.py](../src/pipeline/validation/runner.py) | T0/T2/T3/T4, falhas preexistentes, reexecuções e definições de F. |
| [registro.py](../src/pipeline/registro.py) | Persistência incremental e conferência do commit do alvo. |
| `scripts/setup/` | Preparação do alvo. |
| `scripts/audit/` | Scans, associação, classificação, inventário e verificação das rodadas. |
| `scripts/experiment/` | Catálogo, baseline de testes, medições e tentativas. |
| `scripts/reports/` | Relatórios históricos e cálculo parcial das métricas. |
| `config/` | Mapeamentos, exclusões, prompts e critérios. `config.yaml` está vazio; ainda não é a fonte central de configuração. |
| `rules/` | Regras locais e exemplos positivos/negativos; preservar IDs e versionar conteúdo. |
| `tests/unit/` | Consistência de classificação, relatórios e organização. |
| `tests/integration/rodadaN/` | Inventário padronizado; testes executáveis presentes em 7–12. |
| `tests/integration/historico/` | Fontes originais dos `.mjs` para conferência dos hashes antigos; não são as entradas atuais. |
| `outputs/` | Fontes primárias dos resultados; não sobrescrever para adequar números a mudanças posteriores. |
| `workspace/` | Alvo e cópias temporárias locais, preparados pelo setup. |
| [PoC do TCC1](../../repoc/PoC-TCC-Matheus-e-Caio/README.md) | Referência de fluxo, prompts e métricas Python/Bandit; sem dependência de execução no pipeline atual. |

### Fluxo implementado

```text
Catálogo histórico → worktree limpa → prompt → LLM/cache → patch
                 → Semgrep → compilação/testes → registro R/F/M
                 → restauração → próxima estratégia/caso
```

Até K casos usam worktrees distintas. As estratégias de um caso são sequenciais e partem do código original. T4 é serializado por causa de uma porta fixa usada pelos testes; as demais etapas podem avançar em paralelo. Os patches aceitos ficam em artefatos; não são acumulados automaticamente no alvo.

Hoje, a cadeia para pelo aceite sob a definição mais estrita, `sem_separacao`, e as métricas reconstroem cadeias por definição de F. Isso precisa ser explicitado no protocolo antes de interpretar comparações entre estratégias.

## 5. Comparação com F0–F8 do guia original

| Fase | Estado | O que falta para o próximo ciclo |
|---|---|---|
| F0 — alinhamento | Parcial | Atualizar protocolo para a amostra ampliada e registrar decisões |
| F1 — repositório | Implementado, reorganização local | Revisar, versionar e conferir documentação |
| F2 — ambiente | Scripts e medições históricas | Recriar ambiente e worktrees nesta máquina, conferir versões |
| F3 — SAST e catálogo | Histórico pronto; auditoria ampliada pronta | Gerar e congelar catálogo experimental ampliado |
| F4 — worktrees e validação | Implementado para o fluxo histórico | Cobrir novos arquivos, frontend e mecanismos adicionais |
| F5 — LLM/prompts/RAG | Implementada; preparação validada sem API | Piloto real das quatro estratégias pendente |
| F6 — orquestração | Implementada | Integrar catálogo, identidade e rulesets novos; testar retomada |
| F7 — métricas | Parcial | CSVs, agregações, RRIS e tratamento explícito de indeterminados |
| F8 — piloto das quatro estratégias | Pendente | Executar piloto com artefatos completos e inspeção manual |

O guia propõe três casos × quatro estratégias, enquanto a metodologia prevê parada no primeiro aceite. Definir uma execução de verificação que exercite as quatro estratégias, identificada como piloto, e manter a regra de parada declarada no experimento principal. Não apresentar tentativas adicionais de diagnóstico como se fossem parte da cadeia principal.

## 6. Plano priorizado com critérios de conclusão

### Entrega A — preservar o trabalho e preparar a reprodução (prioridade imediata)

- [ ] Revisar o diff da reorganização, incluindo arquivos novos e exclusões por movimentação.
- [ ] Versionar a reorganização em um commit próprio após revisão.
- [ ] Preparar um ambiente Python completo a partir das dependências e registrar versões efetivas.
- [ ] Conferir Node, npm, Semgrep e o commit fixado do alvo `f915bddd82790d0f3018902d36ae9b4241a5f51f`.
- [ ] Preparar o alvo/worktrees e verificar compilação e testes sem patch.
- [ ] Recuperar os artefatos ausentes de E01/E02 na máquina de origem; registrar os que não puderem ser recuperados.
- [ ] Definir armazenamento dos artefatos oficiais: arquivos pequenos versionados e, para volumes maiores, arquivo externo identificável com hashes e instruções de recuperação.
- [ ] Ajustar o `.gitignore` conforme a política, mantendo dados temporários e credenciais separados das evidências.

**Pronto quando:** outra máquina consegue localizar os dados oficiais e reproduzir a preparação, e o baseline de testes explica as falhas preexistentes. Não executar novamente a LLM apenas para substituir evidências históricas ausentes.

### Entrega B — fechar o catálogo ampliado (primeira entrega científica)

- [x] Usar o scan combinado e a classificação arquivada como fontes identificadas por hash.
- [x] Incluir os 78 alertas dentro do escopo antes da deduplicação: 55 confirmados, 21 falsos positivos e 2 inconclusivos.
- [x] Definir e documentar a unidade experimental. Recomendação: identidade estável por ocorrência de alerta; associação a causa/desafio como metadado, com agrupamentos explicitamente justificados.
- Não aplicável nesta versão: não houve agrupamento; cada ocorrência incluída gera um caso.
- [x] Usar IDs novos/versionados para o conjunto ampliado, preservando JS001–JS012 e suas execuções históricas.
- [x] Preservar casos sem desafio associado, sem CWE ou sem documento RAG específico; definir valores ausentes e fallback.
- [x] Auditar o filtro antigo: severidade, categoria e CWE não podem excluir silenciosamente alertas que a nova política pretende incluir.
- [x] Criar um gerador apropriado à nova política. O atual `build_repair_candidates.py` rejeita alertas não confirmados e exige desafios; sua saída de 16 grupos não serve como entrada final sem adaptação.
- [ ] Versionar catálogo, metadados, regras de inclusão/deduplicação e contagens de reconciliação.

**Pronto quando:** todos os 78 alertas incluídos têm destino rastreável no catálogo; todas as exclusões e agrupamentos são explicados; o número final de casos é reproduzível sem seleção baseada no sucesso da LLM.

### Entrega C — conectar catálogo, regras e comparação antes/depois

- [x] Permitir selecionar explicitamente catálogo e perfil de regras no pipeline e nos scripts de tentativa/sondagem.
- [ ] Congelar o perfil `p/default` e as regras locais usadas no novo experimento, com hashes e versão do Semgrep. O snapshot de referência existente não é automaticamente um snapshot de todo esse perfil.
- [x] Conferir que o mesmo perfil e escopo são utilizados no baseline e na reanálise.
- [ ] Reproduzir os achados esperados sobre o commit limpo; justificar diferenças de parsing, regras e exclusões.
- [ ] Substituir ou adaptar a assinatura legada quando houver ocorrências distintas da mesma regra no mesmo arquivo. Evitar identificar somente por número de linha, que muda com o patch.
- [ ] Testar deslocamento de linhas, correção de uma entre duas ocorrências, permanência do alerta e surgimento de novos findings.
- [ ] Revisar M: a comparação deve seguir a nova política de escopo, sem ocultar novas issues pelo filtro antigo.
- [ ] Definir o alcance da reanálise; hoje ela cobre os arquivos envolvidos, não um scan global após cada patch. Conferir compatibilidade com as regras adotadas e registrar a limitação.
- [x] Registrar na tentativa a versão do catálogo, hashes das regras, commit, identidade do caso e artefatos utilizados.
- [x] Conferir retomada sem duplicação e impedir reaproveitamento de uma execução com catálogo/regras incompatíveis.

**Pronto quando:** um dry-run percorre o catálogo ampliado, produz registros rastreáveis e distingue corretamente os cenários de R/M. Dry-run não chama a API, mas ainda depende do alvo, do Semgrep e dos testes.

### Entrega D — validar o que o catálogo realmente contém

- [ ] Mapear para cada caso os testes funcionais pertinentes, os testes de desafio existentes e a necessidade de validação dinâmica adicional.
- [ ] Reexecutar as integrações 7–12 no ambiente documentado, guardando evidências novas e suas limitações.
- [ ] Avaliar quais casos das rodadas 1–6 precisam de integração nova; escrever testes reais para os mecanismos correspondentes, registrando que são validações posteriores.
- [ ] Cobrir frontend quando presente: testes do servidor não demonstram que HTML renderizado ficou seguro nem preservam sozinhos comportamento Angular.
- [ ] Para ataques demonstrados, incluir controle vulnerável, defesa e comportamento legítimo. Para falsos positivos, preservar funcionalidade e tratar ausência de exploração com honestidade.
- [ ] Atualizar a separação F/D sobre a suíte relevante, conservando critérios e justificativas.
- [ ] Definir como uma falha de D fornece evidência de bloqueio do ataque, distinguindo-a de falha de infraestrutura ou teste mal executado.
- [ ] Declarar a definição principal de F e a análise de sensibilidade; sincronizar regra de parada e cálculo das métricas.

**Pronto quando:** nenhum caso é apresentado como validado dinamicamente sem evidência correspondente. O inventário mantém o mesmo formato em todas as rodadas, mas os testes são específicos do mecanismo. Não criar `test.mjs` vazio só para completar a árvore de arquivos.

### Entrega E — completar a comparação de prompts

- [x] Criar `knowledge_base/` com documentos necessários às categorias do catálogo final e um contexto genérico.
- [x] Registrar fontes, versão/hash dos documentos e cuidados específicos do ecossistema JS/TS.
- [x] Usar exemplos genéricos de mitigação; não fornecer soluções oficiais do Juice Shop nos prompts.
- [x] Implementar recuperação determinística por categoria e montagem efetiva de P3/P4 no builder.
- [x] Registrar documento recuperado, fallback, versão e hash do prompt em cada tentativa.
- [x] Gerar e revisar prompts para todos os casos sem chamar a API.
- [x] Manter restrições, formato JSON e política de contexto consistentes entre estratégias.
- [ ] Congelar os templates e parâmetros antes da execução final; manter P1L como condição diagnóstica separada.

**Pronto quando:** as quatro estratégias geram mensagens completas para o catálogo, inclusive casos sem CWE/contexto específico; testes de recuperação verificam categoria correta e fallback. Critérios da preparação concluídos na feature 03; não equivalem a remediação validada. O congelamento dos parâmetros da execução real permanece pendente.

### Entrega F — piloto e execução final

- [ ] Escolher um pequeno conjunto contrastante e registrar que é piloto, com critérios prévios à observação dos resultados.
- [ ] Exercitar as quatro estratégias e falhas de aplicação, compilação, teste e reanálise.
- [ ] Conferir manualmente os diffs, R/F/M e os arquivos de evidência.
- [ ] Registrar qualquer ajuste do piloto e congelar o protocolo final após essa etapa.
- [ ] Estimar custo/tempo com os novos casos e definir limites de execução e tratamento de interrupções.
- [ ] Executar o conjunto final com identidade nova, mantendo E01/E02 como resultados históricos.
- [ ] Preservar tentativas fracassadas, recusas, JSON inválido, patches não aplicáveis e falhas ambientais; não selecionar somente resultados positivos.
- [ ] Definir se haverá repetições independentes. Cache não conta como nova geração independente.

**Pronto quando:** cada caso está concluído ou tem motivo explícito de não conclusão; todos os registros apontam para evidências acessíveis; a regra de parada foi aplicada e documentada.

### Entrega G — métricas e análise

- [x] Consolidar dados em CSV sem chamar a API, a partir dos registros oficiais.
- [x] Implementar TRV, TRI, TPF, TNINI, TFF, TAP e leitor de RRIS; RRIS real aguarda evidência conjunta. TCD permanece exploratório.
- [x] Declarar denominadores: tentativa, caso, alerta, desafio e execução não são intercambiáveis.
- [x] Tratar explicitamente falhas técnicas, não aplicação e resultados indeterminados; não confundir ausência de medição com sucesso ou falha comprovada.
- [x] Gerar agregações por estratégia, caso, CWE/OWASP, tipo de regra e classificação da auditoria, admitindo dados ausentes.
- [x] Conferir cálculos com um conjunto pequeno de resultados conhecidos.
- [ ] Aplicar o conjunto escolhido de patches aceitos em uma cópia separada, resolver conflitos de forma registrada, testar e reanalisar globalmente para RRIS.
- [ ] Relatar incompatibilidades entre patches: aceites isolados não garantem aceite conjunto.
- [ ] Inspecionar correções aceitas e amostra de rejeitadas; explicar alterações desnecessárias em falsos positivos, falhas de compilação e limites do SAST.

**Pronto quando:** tabelas e gráficos são regeneráveis, os números reconciliam com os registros e as conclusões respeitam as limitações do desenho.

### Entrega H — redação e defesa, em paralelo

- [ ] Escrever implementação usando a arquitetura já existente.
- [ ] Atualizar metodologia com escopo ampliado, regras exploratórias, unidade de análise, inclusão de falsos positivos, F/D e parada da cadeia.
- [ ] Separar resultados da PoC, E01/E02 e experimento ampliado.
- [ ] Apresentar resultados por pergunta de pesquisa, incluindo resultados negativos.
- [ ] Discutir dependência entre estratégias: P2 recebe os casos não resolvidos por P1, e assim por diante; comparar taxas sem explicar isso induz conclusões inadequadas.
- [ ] Discutir o fator combinado de P3/P4: adicionam diagnóstico SAST e documentação, portanto melhora não pode ser atribuída exclusivamente ao RAG sem controle adicional.
- [ ] Registrar possível contaminação de treinamento, projeto único, regras elaboradas após inspeção, parsing incompleto e testes que dependem de vulnerabilidades.
- [ ] Relatar limitações da reanálise por arquivo, da identidade dos findings e dos testes com mocks/precondições específicas.
- [ ] Preparar instruções de reprodução, apresentação, exemplos de sucesso/falha e roteiro de defesa.

**Pronto quando:** cada conclusão tem evidência e cada mudança em relação ao TCC1 tem justificativa registrada. Taxa de sucesso baixa não invalida o trabalho; ausência de método e rastreabilidade compromete sua avaliação.

## 7. Sequência prática e cronograma

```text
A — ambiente/evidências
       ↓
B — catálogo → C — integração SAST/identidade
       ↓                  ↓
D — validação        E — RAG/P3/P4
       └────────┬─────────┘
                ↓
          F — piloto/final → G — métricas

H — redação acompanha as entregas desde o início.
```

Não há estimativa confiável de duração sem medir a validação do novo catálogo. Trabalhar por entregas com evidências evita repetir o cronograma inicial como se todas as condições já estivessem prontas.

O cronograma do TCC1 previa implementação do pipeline/RAG em setembro, experimentos em outubro–novembro, métricas em novembro e análise/redação até dezembro de 2026. Em 13/10/2026, a integração ampliada e RAG passaram pelo preflight sem API. Piloto e avaliação final são as prioridades para atualizar o cronograma com a orientadora; este guia não assume uma data de defesa confirmada.

### Próxima sessão de trabalho

- [ ] Revisar e salvar a reorganização em Git.
- [x] Registrar no protocolo a inclusão de todos os alertas no escopo.
- [x] Produzir uma especificação do catálogo ampliado com identidade, deduplicação e reconciliação dos 78 alertas.
- [x] Implementar o gerador e conferir a saída antes de alterar o orquestrador.

**Próximo marco:** catálogo ampliado versionado, rastreável e pronto para integração. Não expandir mais rodadas apenas para aumentar a contagem antes de concluir esse marco.

## 8. Comandos atuais para consulta e validação

Execute da raiz do repositório, com as dependências instaladas. Os comandos antigos mencionados em `outputs/` são registros históricos; use os caminhos novos abaixo.

```bash
# Testes do próprio projeto.
make test-unit
make test-rules

# Se Semgrep estiver no ambiente local já existente:
make test-rules SEMGREP=.venv-semgrep/bin/semgrep

# Inventário: somente leitura, não executa integração.
python scripts/audit/test_rodada.py --rodada 1
python scripts/audit/test_rodada.py --rodada 7

# Testes de regra e relatório de uma rodada.
python scripts/audit/test_rodada.py --rodada 7 --tipo regras
python scripts/audit/test_rodada.py --rodada 7 --tipo relatorio
```

Comandos que preparam o ambiente ou produzem artefatos devem ser executados conscientemente e com identificação nova:

```bash
# Requer .env preenchido; prepara dependências e worktrees.
bash scripts/setup/setup_target.sh 4

# Requer alvo preparado; gera referência de falhas do ambiente.
python scripts/experiment/baseline_testes.py --help

# Integração: requer checkout fixado e dependências específicas da rodada.
python scripts/audit/test_rodada.py --rodada 8 --tipo integracao \
  --worktree /caminho/juice-shop --deps /caminho/dependencias

# Fluxo histórico, sem chamada à API; ainda executa SAST/testes.
PYTHONPATH=src python -m pipeline.run_pipeline \
  --execucao DRY_REORGANIZACAO_01 --estrategias P1,P2 --dry-run
```

O último comando ainda usa os 12 casos históricos. Não existe atualmente um argumento de catálogo que torne esse comando uma execução dos 78 alertas. As métricas históricas podem ser recalculadas por `scripts/reports/metricas_execucao.py`, mas o comando grava o JSON de métricas; preserve a versão anterior se precisar comparar cálculos.

## 9. Checklist de encerramento do TCC2

- [ ] Protocolo e alterações em relação ao TCC1 documentados.
- [ ] Ambiente e fontes de regras reproduzíveis.
- [ ] Catálogo final congelado com todas as inclusões/exclusões explicadas.
- [ ] Quatro estratégias implementadas e exercitadas.
- [ ] Validação funcional e de segurança adequada ao conjunto escolhido.
- [ ] Execução final concluída com falhas e limitações registradas.
- [ ] Artefatos acessíveis e verificáveis por hash/identidade.
- [ ] Métricas e tabelas regeneráveis, incluindo avaliação consolidada para RRIS.
- [ ] Análise por estratégia/tipo de alerta e discussão de ameaças à validade.
- [ ] Monografia revisada com a orientadora e material de defesa preparado.

Ao marcar um item, acrescente commit, arquivo, execução ou relatório que demonstra a conclusão. Evite usar apenas “funcionou na minha máquina” como evidência.
