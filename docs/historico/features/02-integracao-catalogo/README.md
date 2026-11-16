# Feature 02 — Integrar o catálogo ampliado ao pipeline

**Status:** implementada e validada, com limites registrados no [relatório de entrega](ENTREGA.md).  
**Data:** 12/10/2026.  
**Dependência:** [feature 01 concluída](../01-catalogo-ampliado/ENTREGA.md).  
**Objetivo:** permitir que o pipeline processe os 78 casos ampliados com regras reproduzíveis, comparação por ocorrência e registros próprios.

## 1. Problema

A feature 01 produziu `outputs/catalogos/ampliado_v1/`, mas o orquestrador ainda:

- Lê exclusivamente `outputs/sast_antes/catalogo_issues.json`, com os 12 casos históricos.
- Utiliza cinco rulesets diferentes do perfil `p/default` + regras locais da auditoria ampliada.
- Compara findings por regra × arquivo, fundindo ocorrências distintas.
- Espera `assinatura` e OWASP preenchida para registros e nomes de artefatos.
- Usa filtros antigos de categoria, severidade e CWE para calcular M.
- Reaproveita baseline por existência do arquivo, sem contrato completo de compatibilidade.

Trocar somente o caminho do catálogo não resolve essas diferenças. Esta feature deve ligar catálogo, regras, baseline, tentativas e retomada por uma identidade de execução verificável.

## 2. Decisões e escopo

### Incluído

- Seleção explícita do catálogo e de um perfil local de regras.
- Carregamento e validação do contrato da feature 01.
- Snapshot local, validado, das regras da nova execução.
- Gate de reprodução do catálogo antes de qualquer chamada à LLM.
- Identificação por ocorrência e comparação conservadora após patches.
- Registros de proveniência, classificações indeterminadas e retomada compatível.
- Verificação sem API para todos os casos e dry-run completo em subconjunto.
- Preservação da execução histórica mediante modo legado explícito.

### Fora desta entrega

- RAG/P3/P4 e alteração do conteúdo dos prompts experimentais.
- Nova definição de F ou mudança na parada estrita atual da cadeia.
- Integrações de frontend ou novos oráculos de segurança.
- Execução real das 78 correções, nova análise estatística ou RRIS consolidada.
- Reescrita de E01/E02, do catálogo ampliado ou da auditoria histórica.

**Política:** incluir todos os 78 casos, independentemente da classificação da auditoria. A segurança de uma correção continua dependente das evidências; remover alerta de falso positivo não demonstra remediação de uma vulnerabilidade real.

## 3. Interfaces públicas

### 3.1 Orquestrador

Adicionar argumentos a `python -m pipeline.run_pipeline`:

| Argumento | Comportamento |
|---|---|
| `--catalogo` | Caminho do `catalogo_issues.json`; padrão permanece no histórico para compatibilidade |
| `--perfil-sast` | Caminho de `perfil.json`; obrigatório para catálogo ampliado |
| `--saida` | Diretório de artefatos; obrigatório no modo ampliado e sem mistura com a raiz histórica |
| `--somente-preflight` | Carrega catálogo, verifica ambiente Git/perfil, executa baseline e gera prompts, sem LLM, patch ou testes funcionais |
| `--semgrep-bin` | Executável Semgrep; padrão `semgrep` |
| `--baseline-testes` | Referência funcional da nova validação; padrão histórico para compatibilidade |

Preservar `--execucao`, `--casos`, `--estrategias`, `--diagnosticos`, `--k` e `--dry-run`.

`--pular-checagem-ambiente` pode pular a checagem funcional existente, mas nunca hashes, commit, perfil, gate de reprodução ou identidade da retomada.

Exemplo após implementação:

```bash
PYTHONPATH=src python -m pipeline.run_pipeline \
  --execucao AMP_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/experimentos/AMP_PREFLIGHT_01 \
  --estrategias P1,P2 --somente-preflight --k 1
```

Argumentos relativos explícitos são resolvidos contra o diretório corrente. Validar identificadores de execução como `[A-Za-z0-9][A-Za-z0-9_-]*`; rejeitar caminhos ou componentes `..` nesses identificadores.

### 3.2 Seleção nos scripts auxiliares

Adicionar `--catalogo`, `--perfil-sast` e `--semgrep-bin` aos scripts de tentativa individual e sondagem SAST, utilizando os mesmos loaders e a mesma comparação do orquestrador. Não implementar regras duplicadas de carregamento.

O gerador do catálogo histórico não muda de função e não recebe essa adaptação.

### 3.3 Carregamento

Criar `src/pipeline/catalogo.py` com um objeto de contexto contendo:

- Lista de casos, commit esperado, tipo de catálogo e schema.
- Caminhos e hashes do catálogo, metadados e exclusões quando ampliado.
- Política de escopo e identidade do conjunto.

Modo ampliado: carregar `catalogo_meta.json` e `exclusoes.json` da mesma pasta do catálogo, verificar hashes dos artefatos, schema `1.0`, contagens, IDs únicos, coordenadas e assinaturas conforme feature 01.

Modo histórico: reconhecer a lista de casos com `assinatura` legada; manter o comportamento anterior. Não inserir uma assinatura legada sintética nos casos AMP.

Conferir commit de todos os worktrees contra o catálogo. Se `JUICESHOP_COMMIT` estiver preenchido, ele também precisa coincidir. No modo ampliado, o commit do catálogo é suficiente para conferência e gravação; credenciais continuam restritas às chamadas reais.

## 4. Perfil congelado de regras

### 4.1 Arquivos

```text
config/perfis/ampliado_v1/
├── perfil.json
├── regras_remotas.yaml
└── regras_locais.yaml
```

Criar `scripts/audit/build_sast_profile.py` com entrada `--regras-remotas` obrigatória, `--regras-locais` com padrão `rules/` e `--saida` obrigatória, sempre nova.

O YAML remoto deve conter as definições completas exportadas do perfil `p/default`. A obtenção dessas definições usa `ConfigLoader("p/default").load_config()` do Semgrep 1.177.0 e é uma etapa de preparação registrada no relatório; o builder e o runtime só leem arquivos locais. Não tratar `scan.json`, metadados dos findings ou os snapshots parciais atuais como fonte suficiente para reconstruir regras remotas.

Builder: ler todos os YAMLs locais em ordem de caminho, reunir as definições em um arquivo, manter o `id` de cada regra e recusar IDs duplicados. Ordenar regras por ID e serializar deterministicamente. Não escrever soluções oficiais do alvo nessa pasta.

### 4.2 Manifesto

`perfil.json` deverá conter:

- `schema_versao="1.0"`, `perfil_id="ampliado_v1"` e `semgrep_versao="1.177.0"`.
- `configs`: caminhos relativos e hashes dos dois YAMLs congelados.
- `origem_remota="p/default"`, hash do YAML remoto recebido e indicação explícita de que a exportação foi obtida depois da auditoria, se esse for o caso.
- `id_regras`: lista dos IDs permitidos, sem duplicatas.
- `timeout_regra_s=30` e `timeout_processo_s=900`.
- `escopo`: padrões de exclusão versionados e copiados de `config/semgrepignore`, incluindo `.npmrc` e `frontend/.npmrc` explicitamente.
- `flags`: métricas desativadas, reescrita automática de IDs desativada e respeito ao gitignore do alvo.
- Hash do conteúdo de exclusões e de cada arquivo de regra local de origem.

Não executar textos de comandos armazenados no manifesto. Construir a lista de argumentos a partir dos campos validados.

### 4.3 Runtime e gate

O modo ampliado executa somente os YAMLs locais, com versão conferida, `--no-rewrite-rule-ids`, timeout de regra 30, métricas desativadas e exclusões do perfil. Não adicionar `--no-git-ignore`, pois a auditoria combinada original respeitou o gitignore.

Normalizar IDs para os IDs declarados no perfil. IDs de regras remotas devem corresponder aos IDs observados no catálogo; não criar aliases genéricos por sufixo. Para regras locais, aceitar somente o prefixo já validado pela classificação e o ID `tcc.*` declarado.

Antes de qualquer tentativa, fazer um scan completo do worktree limpo e comparar o multiconjunto de `(regra, arquivo, linhas, colunas)` com os 78 casos. Exigir igualdade completa dentro do escopo: nenhum caso ausente e nenhum alerta novo não catalogado.

Divergência, regra ausente, versão diferente, timeout ou erro operacional impedem chamadas à API e geram relatório de preflight. Não selecionar apenas os casos reencontrados.

**Se o snapshot obtido hoje não reproduzir o catálogo histórico ampliado:** a feature não pode ser declarada pronta para esse catálogo. Preservar o relatório de divergência. Obter a versão correta das regras ou definir explicitamente um novo baseline/catalogo versionado como trabalho separado; nunca atualizar os 78 casos automaticamente para fazer o gate passar.

## 5. Findings e escopo

Estender `Finding` com colunas e offsets opcionais, sem quebrar construtores legados. A serialização deve mostrar as coordenadas disponíveis. Conservar a função de assinatura legada para o modo histórico.

No modo ampliado, a lista de alertas considerados em R/M é formada por todos os findings dentro dos caminhos do perfil. Não filtrar por severidade, CWE, categoria ou veracidade.

Preservar JSON bruto do scan e diagnósticos por arquivo. O parser deve validar IDs, caminhos e coordenadas antes de comparar. Falha de parsing que afete o arquivo do alvo torna R indeterminado. Avisos preexistentes e idênticos em arquivos não alterados são registrados como cobertura limitada. Problemas em arquivos alterados, diagnósticos novos/diferentes ou globais tornam M indeterminado, salvo quando há issue nova confirmada que já determina M=0. Uma ocorrência em arquivo sem cobertura anterior não é considerada nova comprovada.

O preflight arquiva os avisos existentes, inclusive a cobertura incompleta. Erros novos ou diferentes devem ser registrados; uma execução não pode transformar falha de análise em “alerta removido”.

## 6. Comparação após patches

### 6.1 Alcance

No modo ampliado, fazer scan completo antes/depois com o mesmo perfil e escopo. Isso evita perder issues novas em outros arquivos. O custo deve ser medido no dry-run; não reduzir silenciosamente para scan dos arquivos tocados.

Guardar bytes originais dos arquivos alterados antes do patch e bytes resultantes depois. Comparar findings da sessão limpa com os findings posteriores. Não substituir a identidade da feature 01 por hash de código e não comparar somente números de linha.

### 6.2 Pareamento comprovado

Implementar em `src/pipeline/sast/comparacao.py`, sem depender da LLM:

1. Agrupar findings por regra normalizada e arquivo.
2. Arquivo não alterado: parear por coordenadas completas iguais, em relação um-para-um.
3. Arquivo alterado: calcular blocos iguais com `difflib.SequenceMatcher(autojunk=False)` sobre linhas com finais preservados.
4. Aceitar um bloco como âncora somente quando sua sequência completa ocorre uma única vez no arquivo original e uma única vez no posterior. Contar ocorrências por sequência de linhas, incluindo sobreposições; não por busca textual parcial.
5. Um finding só pode ser mapeado quando seu intervalo inteiro estiver dentro desse bloco; traduzir linhas pelo deslocamento do bloco e manter colunas, pois as linhas são idênticas.
6. Parear somente se existir uma única ocorrência posterior da mesma regra com as coordenadas traduzidas e sem disputa entre findings anteriores.
7. Nunca escolher o candidato mais próximo, parear por ordem ou atribuir identidades por mensagem genérica.

Esse algoritmo privilegia comprovação. Se linhas idênticas repetidas impedirem uma âncora única, a comparação deve manter a ambiguidade explícita.

### 6.3 Ocorrências não pareadas

Após retirar os pares comprovados, avaliar cada grupo regra/arquivo:

| Situação | Resultado |
|---|---|
| Só sobram anteriores | Ocorrências removidas |
| Só sobram posteriores | Ocorrências novas |
| Sobram anteriores e posteriores | Correspondência indeterminada; pode ser permanência ou substituição |
| Não sobra nenhuma | Grupo completamente pareado |

Para o caso-alvo: `R=0` quando pareado; `R=1` quando removido; `R=null` quando indeterminado ou análise do arquivo inconclusiva.

Para M: `M=0` se existir qualquer nova ocorrência confirmada; `M=null` se não houver nova comprovada, mas houver grupo/arquivo indeterminado; `M=1` quando a comparação estiver completa e sem novas.

`novas_issues_qtd` representa somente novas comprovadas. Adicionar `possiveis_novas_issues_qtd` para posteriores não pareadas de grupos ambíguos. Uma alteração no trecho pode continuar disparando a mesma regra e produzir R/M indeterminados; isso é uma limitação declarada, não justificativa para usar heurística otimista.

### 6.4 Evidência

Gravar por tentativa um JSON de comparação com:

- IDs e coordenadas dos anteriores/posteriores.
- Pares, removidos, novos e grupos ambíguos.
- Blocos utilizados, deslocamentos e motivos de não pareamento.
- Diagnósticos de parsing e R/M resultantes.

Ocorrências posteriores recebem IDs próprios de diagnóstico; não reutilizar um `caso_id` do baseline sem correspondência comprovada.

## 7. Tentativas, prompts e classificação

Preservar campos da feature 01. `assinatura_ocorrencia` vai para o registro como identidade do baseline; não preencher `assinatura` legada no modo ampliado.

Quando OWASP for nula, usar somente no nome do artefato o token `SEMOWASP`; o valor registrado continua `null`. Manter o formato:

```text
<CASO>_<OWASP-ou-SEMOWASP>_<SIGLA>_<PROMPT>_<EXECUCAO>
```

Registrar `classificacao_auditoria`, desafios, fonte do caso e os três hashes: catálogo, metadados e perfil. Também registrar `comparacao_status`, `comparacao_artefato`, cobertura da validação e motivos de indeterminação.

Aceite automático exige R=1, F=1 e M=1. Se R ou M forem nulos, usar `indeterminada_sast`; não parar a cadeia por esse resultado. Preservar os campos das três definições de F.

No modo ampliado, funções de resumo reconhecem `indeterminada_sast` e reportam sua contagem. Na TRV, uma tentativa indeterminada não é remediação validada e permanece no denominador. TRI/TPF/TNINI são calculadas sobre valores medidos, com denominadores explícitos e `null` quando não houver medição. As taxas históricas mantêm os cálculos anteriores.

Não fornecer a classificação da auditoria ou soluções oficiais ao prompt. Não mudar o conteúdo de P1/P2/P1L nesta feature. Roteiro e estrutura de resposta continuam comuns às estratégias existentes.

**Limite funcional:** casos de frontend podem ser carregados e exercitados, mas T0/T2/T3/T4 atuais cobrem o servidor. Registrar `cobertura_funcional="servidor"`; não apresentar F=1 como validação integral de frontend. A execução final desses casos depende da feature de validação correspondente.

## 8. Preflight, dry-run e retomada

### Preflight

`--somente-preflight` usa um worktree do pool e verifica commit, hashes dos fontes do catálogo, perfil e reprodução SAST. Monta e salva prompts de P1/P2 para todos os casos selecionados.

Não exige API key, não instancia cliente LLM, não aplica resposta falsa e não executa testes funcionais. Continua exigindo Semgrep e checkout adequado. Criar relatório com selecionados, contagens, incompatibilidades, hashes e diagnósticos. Saída 0 somente se todas as verificações passarem.

### Dry-run

`--dry-run` continua executando patch simulado, SAST e validação, mas sem API. A edição falsa deve usar âncora única com contexto do finding e inserir comentário seguro em linha própria para JS/TS. Não acrescentar `//` a uma linha de template HTML/Pug/YAML.

Para casos de linguagens sem edição simulada segura implementada, registrar `dry_run_sem_patch_suportado`, salvar prompt/registro e não inventar sucesso R/F/M. O preflight é o critério de cobertura de carregamento dos 78 casos; o dry-run ponta a ponta é verificado em casos JS/TS escolhidos.

### Retomada

Em modo ampliado, todos os artefatos ficam sob `--saida`, incluindo `resultados_consolidados/execucoes.jsonl`, baseline e relatório da sessão. Criar um `contrato_execucao.json` antes das tentativas.

O contrato contém execução, modo, commit, hashes do catálogo/metadados/perfil, Semgrep, estratégias, diagnósticos, conjunto ordenado de casos, versão do comparador e hashes das restrições/roteiro dos prompts. K pode variar na retomada, pois muda capacidade e não a definição do experimento.

Retomar somente com contrato idêntico e arquivos do baseline com hashes conferidos. Conferir também os contratos das linhas já gravadas. Não aceitar linhas históricas sem proveniência como tentativas dessa execução.

Não sobrescrever prompt ou resposta de uma tentativa concluída. Baseline não é reutilizável só porque o arquivo existe. Divergência de contrato exige nova execução e novo diretório.

## 9. Componentes e estratégia de implementação

- `catalogo.py`: loader e validação, com adaptação explícita de histórico/ampliado.
- `sast/perfil.py`: perfil local, IDs, flags, hashes e escopo.
- `sast/comparacao.py`: pareamento conservador e relatório.
- Cliente Semgrep: coordenadas, executável/flags por perfil e resultado com diagnósticos.
- Orquestrador: contextos, gate, comparação, nomes e saída selecionada.
- Registro: commit esperado opcional recebido do catálogo no modo ampliado.
- Scripts auxiliares e métricas: usar os mesmos loaders; permitir leitura da saída selecionada para analisar a nova execução.

Evitar cópias inteiras do orquestrador. Preservar o caminho legado por contexto explícito, sem usar o perfil novo nas execuções antigas.

## 10. Testes e cenários de aceite

### Catálogo e perfil

- [ ] Histórico e ampliado carregados em modos distintos, com 12 e 78 casos respectivamente.
- [ ] Falsos positivos, inconclusivos e INFO preservados; OWASP nula não quebra nomes ou registros.
- [ ] Catálogo adulterado, IDs duplicados, commit incorreto e perfil incompatível interrompem antes da API.
- [ ] Snapshot local contém IDs únicos e hashes conferidos; alteração posterior impede execução/retomada.
- [ ] Perfil sem uma regra requerida não pode liberar tentativas.
- [ ] Gate exige igualdade de todos os 78 findings, admitindo ordem distinta do JSON.
- [ ] Casos ausentes ou adicionais geram relatório e abortam; nenhuma seleção favorável é feita.

### Comparação

- [ ] Alerta permanece sem alteração: R=0.
- [ ] Inserção/remoção de linhas antes de alerta em bloco único: pareamento preservado.
- [ ] Corrigir uma de duas ocorrências: apenas a removida recebe R=1; a outra permanece.
- [ ] Surgimento de segunda ocorrência de regra já existente resulta em M=0.
- [ ] Mesmo número de findings com remoção e introdução comprovadas não implica M=1.
- [ ] Finding dentro de trecho alterado e candidato não pareado da mesma regra: indeterminação.
- [ ] Blocos idênticos repetidos não causam escolha arbitrária de identidade.
- [ ] Parsing/timeout impede declaração automática de remoção ou ausência de novas issues.
- [ ] Reanálise global detecta findings novos fora dos arquivos editados.

### Orquestração

- [ ] Preflight monta P1/P2 para os 78 casos sem cliente LLM ou alterações no alvo.
- [ ] Dry-run JS/TS com patch aplicável, comparação e testes; worktree restaurado após sucesso ou erro.
- [ ] Templates sem patch simulado suportado são registrados explicitamente, sem comentário inválido.
- [ ] Falha/indeterminação não para a cadeia; aceite mantém a regra estrita existente.
- [ ] Retomada compatível não repete tentativas; incompatível é recusada.
- [ ] Diretórios de execução diferentes não misturam registros ou sobrescrevem E01/E02.
- [ ] Histórico continua com assinatura/regra de comparação anteriores, sob testes de regressão.

### Execução de validação

A validação real percorreu as etapas; uma tentativa simulada foi reprovada em F por um teste de hint dependente de linha. Essa reprovação foi preservada, não representa erro de orquestração.

- [x] `make test-unit` passando com testes sintéticos de comparação e subprocessos simulados.
- [x] Preflight real completo sobre 78 casos com perfil congelado reproduzido.
- [x] Dry-run real em subconjunto JS/TS, sem chamada à API, com dependências do alvo preparadas separadamente.
- [x] Evidências anteriores preservadas e worktrees limpos após execução.
- [x] Relatório de entrega registra duração, custo zero de API, hashes, comandos e limitações.

Não marcar aceite se o snapshot atual não reproduzir o catálogo. Não substituir preflight ou dry-run real por resultados de mocks sem declarar a pendência.

## 11. Documentação e conclusão

Atualizar protocolo com perfil congelado, escopo, correspondência conservadora, indeterminação e limite de cobertura funcional. Acrescentar comandos ao README e conferir links/caminhos. Criar `ENTREGA.md` somente com os resultados efetivamente verificados.

**Pronto quando:** os 78 casos podem ser carregados e pré-validados sob o perfil local, as tentativas usam identidade de ocorrência com R/M auditáveis, a retomada preserva o contrato e o dry-run do subconjunto funciona. As quatro estratégias e a validação integral dos novos casos seguem como próximas entregas.
