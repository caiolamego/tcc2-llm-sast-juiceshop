# Feature 01 — Gerar o catálogo experimental ampliado

**Status:** implementada e validada; ver [relatório de entrega](ENTREGA.md).  
**Data:** 12/10/2026.  
**Objetivo:** transformar os achados da auditoria em uma lista determinística e rastreável de casos de correção.  
**Origem:** [guia de continuidade](../../../planejamento/GUIA_CONTINUIDADE_TCC2.md), entrega B.  
**Entrega seguinte:** integrar este catálogo ao orquestrador e adaptar R/M e o perfil de regras.

## 1. Problema e resultado esperado

O pipeline atual lê o catálogo histórico de 12 casos. A auditoria ampliada já possui um scan de 124 alertas, dos quais 78 estão dentro do escopo, mas esses dados ainda não são um catálogo experimental apropriado à decisão atual do grupo.

O gerador exploratório `build_repair_candidates.py` seleciona apenas alertas confirmados associados a desafios. Ele não atende à política adotada: tentar corrigir **todos os alertas dentro do escopo**, inclusive falsos positivos e inconclusivos.

Implementar um gerador independente, sem chamada à LLM ou nova execução do Semgrep, que produza:

1. Um catálogo com uma entrada por ocorrência incluída.
2. Um registro separado de todas as exclusões.
3. Metadados de origem, configuração, identidade e reconciliação das contagens.

Para os arquivos oficiais desta feature, a saída deve ter **78 casos e 46 exclusões**, totalizando os 124 alertas de entrada. Essa contagem é uma expectativa da fixture oficial; o gerador também deve aceitar fixtures menores em testes, sem números fixos na lógica de produção.

## 2. Decisões de escopo

### Incluído

- Leitura do scan, classificação, resumo e manifesto arquivados.
- Validação da correspondência entre essas fontes e o checkout do alvo.
- Inclusão determinada exclusivamente pelo status de escopo da classificação validada.
- Identificação estável de cada ocorrência no baseline fixado.
- Extração de código do checkout para os casos incluídos.
- Normalização de metadados com valores ausentes explícitos.
- Saídas JSON determinísticas, imutabilidade de arquivos anteriores e testes.

### Não faz parte desta feature

- Executar Semgrep, instalar dependências, clonar ou modificar o Juice Shop.
- Chamar a LLM, gerar prompts, aplicar patches ou rodar testes do Juice Shop.
- Agrupar por causa, arquivo, CWE, desafio ou par regra/arquivo.
- Alterar E01/E02, JS001–JS012, o catálogo histórico ou o gerador exploratório anterior.
- Implementar `--catalogo` no orquestrador, RAG/P3/P4 ou novas métricas.
- Resolver identidade de findings após alteração do código; a assinatura aqui identifica o baseline.
- Congelar ou revalidar as regras remotas da auditoria. Registrar essa limitação nos metadados.

## 3. Fontes e entradas

Todos os caminhos seguintes são relativos à raiz do repositório.

| Entrada | Padrão | Papel |
|---|---|---|
| Scan | `outputs/auditoria_sast/combinado-hZGD7r/scan.json` | Findings brutos, colunas, mensagens, severidade e metadados |
| Classificação | `outputs/auditoria_sast/combinado-hZGD7r/triagem-final/alertas_classificados.json` | Escopo, regra normalizada, arquivo relativo, justificativa e vínculos |
| Resumo | `outputs/auditoria_sast/combinado-hZGD7r/triagem-final/resumo.json` | Commit, versão, hash do scan e totais esperados |
| Manifesto do scan | `outputs/auditoria_sast/combinado-hZGD7r/manifesto.json` | Proveniência da execução arquivada |
| Checkout do alvo | Obrigatório por `--worktree` | Fonte efetiva dos trechos |
| Raiz original do scan | `/tmp/tcc-juiceshop-audit` | Normalização dos caminhos absolutos gravados no JSON |
| Mapas | `config/mapa_cwe_vuln.yaml`, `config/mapa_owasp.yaml`, `config/mapa_categoria_rag.yaml` | Enriquecimento descritivo; nunca exclusão |

A raiz original é uma informação de proveniência: não precisa existir nesta máquina. O checkout atual pode estar em qualquer caminho. Não inferir a raiz por sufixos de nome de arquivo ou por proximidade de diretórios.

Não depender de `.env` nem de credenciais. A referência do commit é o conjunto de metadados arquivados, não o estado da branch do pipeline.

## 4. Interface de linha de comando

Criar `scripts/experiment/build_expanded_catalog.py`, usando o bootstrap e `RAIZ_REPO` existentes.

```bash
python scripts/experiment/build_expanded_catalog.py \
  --worktree workspace/wt-1 \
  --saida outputs/catalogos/ampliado_v1
```

| Argumento | Regra |
|---|---|
| `--worktree` | Obrigatório; diretório existente contendo o checkout do alvo |
| `--saida` | Obrigatório; diretório novo, ainda inexistente |
| `--scan` | Opcional; padrão indicado na seção 3 |
| `--classificacao` | Opcional; padrão indicado na seção 3 |
| `--resumo` | Opcional; padrão indicado na seção 3 |
| `--manifesto-scan` | Opcional; padrão indicado na seção 3 |
| `--raiz-scan` | Opcional; padrão indicado na seção 3; deve ser absoluto quando o scan contém caminhos absolutos |

Padrões são ancorados em `RAIZ_REPO`. Argumentos relativos explicitamente fornecidos pelo usuário são resolvidos contra o diretório corrente. `--help` não precisa de checkout ou fontes presentes.

Não criar `--force`. Recusar saída existente, mesmo vazia, para preservar execuções. Não usar caminhos absolutos da máquina atual nos JSONs produzidos.

**Códigos de saída:** 0 para sucesso; 2 para argumentos inválidos; 1 para inconsistência de dados, problemas de leitura/Git ou escrita. Em falha, mostrar o arquivo e a ocorrência relevantes em stderr, sem produzir um catálogo parcial.

**Resumo em stdout:** quantidade bruta, incluídos, excluídos e distribuição dos incluídos por classificação, além do diretório de saída. Não imprimir código-fonte.

## 5. Algoritmo e validações

### 5.1 Proveniência

1. Ler e calcular SHA-256 dos bytes exatos das quatro fontes JSON e dos três mapas YAML.
2. Conferir que `scan_sha256` do resumo e do manifesto corresponde ao scan recebido.
3. Conferir igualdade do commit e versão do Semgrep entre resumo e manifesto; a versão do scan deve ser a mesma.
4. Conferir `git rev-parse HEAD` do checkout contra o commit arquivado.
5. Exigir checkout sem modificações rastreadas ou arquivos novos não ignorados, usando `git status --porcelain`. Dependências ignoradas podem existir.
6. Verificar todas as contagens declaradas: resultados do scan, quantidade da classificação, `alertas_brutos` do resumo, `findings` do manifesto e distribuição `triagem` do resumo.

Não executar a string `comando` do manifesto. O manifesto descreve a execução anterior; não autoriza operações.

### 5.2 Associação exata entre classificação e scan

`numero` na classificação aponta para `scan.results[numero - 1]`. Exigir inteiros únicos cobrindo exatamente `1..N`, sem lacunas ou entradas extras.

Para cada associação, conferir:

- `regra_original == check_id` bruto.
- Caminho bruto normalizado igual a `arquivo` da classificação.
- `inicio/fim` iguais às linhas `start/end` do finding.
- Regra normalizada não vazia. Aceitar igualdade ao ID original ou, para regras locais `tcc.*`, o ID original terminando em `.` seguido do ID normalizado, conforme o classificador existente. Outras divergências são erro.
- Linha e coluna positivas, intervalo ordenado e offsets não negativos/ordenados quando presentes.
- Status entre `confirmado`, `falso_positivo`, `inconclusivo`, `fora_escopo`.

Normalização de caminho deve usar componentes, não `endswith`: remover somente a raiz original declarada nos caminhos absolutos; em caminhos relativos, aceitar prefixo `./`. Rejeitar saída da raiz, segmentos `..` e caminho absoluto restante. Armazenar sempre o caminho relativo em formato POSIX.

### 5.3 Inclusão e exclusão

| Status | Ação |
|---|---|
| `confirmado` | Incluir |
| `falso_positivo` | Incluir |
| `inconclusivo` | Incluir |
| `fora_escopo` | Registrar em exclusões, com justificativa não vazia |

Não reaplicar `pipeline.sast.filtro.filtrar`, nem inferir novos cortes de `config/semgrepignore`. A classificação arquivada e validada é a decisão de escopo desta versão.

Severidade baixa, falta de CWE/OWASP, ausência de desafio ou ausência de categoria RAG não excluem um caso. Erro estrutural interrompe a geração; nunca converte um alerta silenciosamente em exclusão ou ignora a entrada.

Não há deduplicação nesta versão. Se duas entradas tiverem a mesma identidade de ocorrência definida abaixo, interromper com erro e apontar seus números. Regras diferentes no mesmo local permanecem casos distintos; ocorrências da mesma regra em locais diferentes também.

### 5.4 Código e contexto

Somente para os incluídos:

- Resolver o arquivo dentro do checkout; rejeitar arquivo ausente, não regular ou link simbólico que resolva fora da raiz.
- Ler bytes, registrar SHA-256 do arquivo e decodificar UTF-8 estritamente, preservando quebras de linha. Erro de leitura/encoding é falha explícita.
- Conferir limites de linhas e offsets contra o arquivo. Colunas são preservadas conforme Semgrep; não reinterpretar como índices Unicode para recortar strings.
- Recortar linhas completas com três linhas de folga antes/depois, limitadas ao arquivo. Registrar as linhas exatas do trecho.
- Definir `modo_contexto` como `arquivo_completo` para até 250 linhas e `janela_contexto` acima disso. Esse campo é uma indicação; não altera o recorte de três linhas gravado no catálogo.
- Não usar `extra.lines` como fonte do código: pode conter `requires login`.

Não ler trechos de arquivos excluídos, especialmente `data/static/codefixes/`. A justificativa de exclusão basta para a rastreabilidade desses arquivos.

## 6. Identidade e determinismo

Definir a identidade como SHA-256 da seguinte lista serializada por `json.dumps(..., ensure_ascii=False, separators=(",", ":"))`, codificada em UTF-8:

```text
[commit_alvo, regra_normalizada, arquivo_relativo,
 linha_inicio, coluna_inicio, linha_fim, coluna_fim]
```

- `assinatura_ocorrencia`: digest completo hexadecimal de 64 caracteres.
- `caso_id`: `AMP` seguido dos primeiros 16 caracteres do digest; exemplo apenas de formato: `AMP0123456789abcdef`.
- Detectar colisão de ID curto entre digests diferentes e interromper, sem renumerar automaticamente.
- Não usar o número sequencial da classificação, o nome da máquina, timestamps ou a ordem do JSON para construir o ID.
- Ordenar catálogo e exclusões por `(arquivo, linha_inicio, coluna_inicio, linha_fim, coluna_fim, check_id)`.

A identidade é estável no mesmo commit e intervalo, inclusive em outro diretório de checkout. **Não é resistente ao deslocamento de linhas após um patch.** A comparação posterior de R/M requer outra feature; não reutilizar esta assinatura cegamente como solução desse problema.

Resultados com as mesmas entradas e fontes devem ser byte a byte iguais, inclusive metadados. Não gravar hora atual, duração, caminho de saída nem caminho absoluto do checkout. Registrar versão do schema e hashes das entradas. Mudanças nos mapas devem mudar o hash do catálogo gerado, mas não o ID de uma ocorrência inalterada.

## 7. Contrato das saídas

```text
<saida>/
├── catalogo_issues.json    # lista dos casos incluídos
├── exclusoes.json         # lista dos alertas fora do escopo
└── catalogo_meta.json      # proveniência e reconciliação
```

Gravar JSON UTF-8 com `ensure_ascii=False`, `indent=2`, `sort_keys=True` e uma quebra de linha final. Listas de casos seguem a ordenação da seção 6.

### 7.1 Campos de cada caso

Todos os campos abaixo são obrigatórios; usar `null` ou `[]` conforme especificado para valores ausentes.

| Campo | Tipo/conteúdo |
|---|---|
| `caso_id` | ID `AMP…` definido na seção 6 |
| `assinatura_ocorrencia` | SHA-256 completo |
| `commit_alvo` | Commit fixado |
| `check_id` | Regra normalizada da classificação |
| `check_id_original` | Regra bruta do scan |
| `arquivo` | Caminho relativo POSIX |
| `linha_inicio`, `coluna_inicio`, `linha_fim`, `coluna_fim` | Inteiros, sem alteração da convenção Semgrep |
| `offset_inicio`, `offset_fim` | Inteiros presentes no scan; `null` se ausentes |
| `severidade` | String bruta ou `null` |
| `categoria_sast` | `extra.metadata.category` ou `null` |
| `mensagem` | Mensagem bruta, ou string vazia se ausente |
| `cwe` | Lista de strings originais de CWE |
| `cwe_ids` | IDs `CWE-N` extraídos, únicos, preservando a ordem de origem |
| `owasp_original` | Lista de strings originais |
| `owasp_2025` | Código primário derivado ou `null` |
| `sigla_vuln` | Primeira sigla mapeável na ordem de `cwe_ids`; `OUTRO` se nenhuma |
| `categoria_rag` | Valor não nulo do mapa para a sigla; `generico` quando ausente/nulo |
| `classificacao_auditoria` | Um dos três status incluídos |
| `justificativa_auditoria` | Motivo preservado da classificação |
| `desafios` | Lista de chaves da classificação, podendo ser vazia |
| `referencias_historicas` | Lista preservada da classificação, podendo ser vazia |
| `trecho` | Código extraído conforme seção 5.4 |
| `trecho_linha_inicio`, `trecho_linha_fim`, `linhas_arquivo` | Inteiros |
| `arquivo_sha256` | Hash dos bytes do fonte |
| `modo_contexto` | `arquivo_completo` ou `janela_contexto` |
| `elegivel` | Sempre `true`; elegibilidade por escopo nesta versão |
| `motivo_exclusao` | Sempre `null` |
| `origem` | Objeto `{"numero_alerta": N, "indice_resultado_scan": N-1}` |

Normalizar CWE/OWASP ausentes ou nulos para `[]`; uma string vira lista de um elemento; lista com itens não textuais é erro. Demais campos presentes com tipos inválidos devem gerar erro explícito.

OWASP: priorizar o primeiro rótulo explícito `Axx:2025`; se não houver, usar o primeiro rótulo 2021 com correspondência no mapa. Sem correspondência: `null`. Preservar rótulos originais, inclusive múltiplos ou divergentes; não fazer reclassificação manual. O gerador não exige que o documento RAG exista nesta etapa.

Não criar o campo legado `assinatura`: seu nome induziria uso indevido da identidade antiga pelo pipeline. Este catálogo **não é plug-and-play** no orquestrador atual. Não inventar modo/sanitizadores de regra a partir de snapshots que podem não corresponder à execução.

### 7.2 Campos das exclusões

Usar: `assinatura_ocorrencia`, `commit_alvo`, `check_id`, `check_id_original`, `arquivo`, coordenadas e offsets, `classificacao_auditoria="fora_escopo"`, `motivo_exclusao`, `origem`.

Não atribuir `caso_id`, nem incluir trecho ou conteúdo de arquivos excluídos. A identidade serve para rastrear a ocorrência descartada, não para transformá-la em tentativa.

### 7.3 Metadados do catálogo

Contrato de `catalogo_meta.json`:

- `schema_versao`: `"1.0"`.
- `catalogo_tipo`: `"ampliado_por_ocorrencia"`.
- `politica_versao`: `"escopo_apenas_v1"`.
- `unidade`: `"ocorrencia_regra_arquivo_intervalo_no_commit"`.
- `commit_alvo`, `semgrep_versao`: valores verificados das fontes.
- `raiz_original_scan`: valor da opção `--raiz-scan`, normalizado; informação histórica, não checkout atual.
- `fontes`: objetos por papel (`scan`, `classificacao`, `resumo`, `manifesto_scan`, `mapa_cwe`, `mapa_owasp`, `mapa_rag`) com `arquivo` e `sha256`. Usar caminho relativo ao repositório quando interno e apenas basename quando externo; o hash distingue fontes homônimas.
- `contagens`: `alertas_brutos`, `casos_incluidos`, `alertas_excluidos`, `por_classificacao` (as quatro chaves de status, incluindo zeros), `por_severidade` (ausente como `SEM_DADO`), `incluidos_sem_cwe`, `incluidos_sem_owasp`, `incluidos_rag_generico`, `avisos_parsing` (quantidade de itens em `scan.errors`).
- `arquivos_fonte`: mapa ordenado dos caminhos incluídos para seus hashes; cada arquivo aparece uma vez.
- `artefatos`: hashes SHA-256 de `catalogo_issues.json` e `exclusoes.json` já serializados. Não incluir auto-hash de `catalogo_meta.json`.
- `limitacoes`: lista fixa de três mensagens: identidade restrita ao baseline; perfil remoto histórico não congelado; ausência de integração automática com o orquestrador atual.

Reconciliação obrigatória: `alertas_brutos == casos_incluidos + alertas_excluidos`, e a distribuição de status deve coincidir com o resumo recebido. Limitação de parsing deve ser registrada, sem apresentar o scan como análise completa.

## 8. Escrita, imutabilidade e falhas

- Fazer toda validação e montagem antes de publicar os três arquivos.
- Escrever em diretório temporário irmão da saída; promover somente após serialização e verificações concluídas. Limpar o temporário se ocorrer exceção.
- Reservar a execução com um arquivo irmão `<nome-saida>.lock`, criado com `os.open` usando `O_CREAT | O_EXCL`. Duas instâncias do gerador para o mesmo destino não podem prosseguir simultaneamente. Com a reserva ativa, conferir novamente que o destino não existe e promover o temporário com rename no mesmo filesystem.
- Remover o lock em `finally`. Se houver interrupção abrupta e sobrar lock, a execução seguinte falha com instrução para verificar se existe processo ativo antes da remoção manual; não apagar lock automaticamente. Um destino criado externamente durante o processamento deve causar falha na checagem anterior à promoção.
- Revalidar HEAD, limpeza do checkout e hashes dos arquivos lidos imediatamente antes da publicação para detectar alterações concorrentes no alvo.
- Nunca restaurar, limpar, aplicar checkout ou modificar o alvo para satisfazer a validação. Informar a inconsistência ao usuário.
- Preservar todos os arquivos de entrada, artefatos anteriores, `.env` e catálogo histórico.
- Não tratar falta de arquivo, classificação ambígua ou erro de JSON como “caso sem código” elegível para execução.

## 9. Organização sugerida da implementação

| Arquivo | Responsabilidade |
|---|---|
| `scripts/experiment/build_expanded_catalog.py` | CLI e funções de leitura, validação, montagem e escrita; entrada protegida por `if __name__ == "__main__"` |
| `tests/unit/test_expanded_catalog.py` | Testes de regras de inclusão, identidade, proveniência e CLI |
| `docs/protocolo_experimental.md` | Registrar a nova política como versão ampliada; preservar descrição histórica |
| `docs/GUIA_CONTINUIDADE_TCC2.md` | Atualizar checklist somente após evidências de conclusão |

Separar funções testáveis de leitura/Git/escrita. Não importar o gerador antigo para reutilizar decisões de filtragem ou a exigência de `.env`. Reutilizar apenas utilitários neutros quando não carregarem essas decisões.

Não gerar novos diretórios de negócio vazios ou refatorar outros subsistemas para implementar esta feature.

## 10. Testes e cenários obrigatórios

### Inclusão e normalização

- [x] Confirmado, falso positivo e inconclusivo incluídos; fora de escopo excluído.
- [x] Alerta INFO/LOW, sem CWE, sem OWASP ou sem desafio permanece incluído.
- [x] CWE/OWASP em string, lista, nulo e ausente tratados conforme contrato; tipo inválido rejeitado.
- [x] Fallback `OUTRO`/`generico` e prioridade de rótulo OWASP 2025 conferidos.
- [x] Dois alertas da mesma regra em linhas diferentes geram dois casos.
- [x] Duas regras no mesmo intervalo geram dois casos; identidade exata duplicada falha.
- [x] Classificação/scan com associação divergente, número repetido, ausente ou desconhecido falha.

### Identidade e fontes

- [x] Reordenar somente a lista da classificação preserva saída, pois `numero` resolve a associação. O hash dessa fonte muda nos metadados, portanto comparar estabilidade dos IDs/conteúdo dos casos, não igualdade dos metadados nessa variante.
- [x] Executar sobre cópias limpas do mesmo commit em diretórios diferentes mantém os bytes da saída.
- [x] Regra local com prefixo compatível é aceita; regra arbitrariamente diferente é rejeitada.
- [x] Hash do scan divergente, versão divergente, commit incorreto e checkout modificado falham.
- [x] Arquivo ausente, UTF-8 inválido, intervalo fora dos limites e path traversal falham.
- [x] Arquivo excluído pode estar ausente no checkout: não deve ser aberto para extrair código.
- [x] Troca de mapa altera enriquecimento/proveniência, sem mudar identidade da mesma ocorrência.
- [x] Alteração do checkout durante a geração impede a publicação.

### Saída e interface

- [x] Duas gerações com as mesmas entradas em destinos diferentes produzem os mesmos três arquivos byte a byte.
- [x] Destino existente é rejeitado e não modificado; falha de validação não deixa saída final parcial.
- [x] Hashes dos dois artefatos coincidem com os metadados.
- [x] Comando funciona a partir de outro diretório usando argumentos absolutos; `--help` funciona sem alvo.
- [x] Nenhum teste chama Semgrep, API ou modifica um checkout real do projeto.

### Reconciliação com dados oficiais

- [x] As fontes arquivadas reconciliam 124 alertas: 78 incluídos, 46 excluídos; 55/21/2 entre incluídos.
- [x] Os 46 excluídos mantêm os motivos originais e não possuem trechos.
- [x] IDs de todas as 124 identidades são únicos; há exatamente 78 `caso_id`.
- [x] Catálogo histórico e fontes têm os mesmos hashes antes/depois.

Usar fixtures sintéticas e repositórios Git temporários nos testes unitários. O teste de reconciliação das fontes oficiais pode validar a associação sem checkout. A extração real de trechos exige um checkout do commit fixado; se ausente, registrar essa verificação como pendente, nunca simular sua execução como concluída.

## 11. Critérios de aceite e evidências de entrega

- [x] CLI, contrato e comportamento implementados conforme esta especificação.
- [x] Testes novos e `make test-unit` passando.
- [x] Geração real concluída em diretório novo sobre checkout limpo e commit correto.
- [x] Contagem oficial 78/46 verificada, incluindo os 21 falsos positivos e os dois inconclusivos.
- [x] Reprodutibilidade byte a byte comprovada em duas saídas novas.
- [x] Referências e hashes conferidos; nenhum artefato histórico sobrescrito.
- [x] Protocolo atualizado com a política ampliada e unidade por ocorrência.
- [x] Relatório de entrega registra comando, ambiente, contagens e localização da saída.

**Não aceitar como conclusão:** apenas criar JSON com 78 itens, copiar o catálogo de 12, reaproveitar os 16 grupos confirmados ou afirmar que o pipeline já consome a saída.

## 12. Dependências e continuação

Esta feature pode ser implementada e testada sem chave de API. A geração oficial depende de um checkout limpo do Juice Shop no commit arquivado. A pasta `workspace/` estava ausente na análise anterior; conferir novamente antes de executar.

Após o aceite, a próxima feature deverá definir seleção de catálogo no orquestrador, consumo do schema, congelamento do perfil ampliado e identidade de findings após patches. Esses itens são necessários antes de usar os 78 casos em uma execução de correção.
