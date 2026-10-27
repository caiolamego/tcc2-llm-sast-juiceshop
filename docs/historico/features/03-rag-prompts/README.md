# Feature 03 — RAG simplificado e prompts P3/P4

**Status:** implementada e validada sem API; [evidências de entrega](ENTREGA.md).  
**Data:** 13/10/2026.  
**Dependências:** [catálogo ampliado](../01-catalogo-ampliado/ENTREGA.md) e [integração do pipeline](../02-integracao-catalogo/ENTREGA.md).  
**Objetivo:** completar as quatro estratégias do TCC1 com recuperação documental determinística e rastreável, validada inicialmente sem API.

## 1. Problema e entrega

No início desta feature, `src/pipeline/prompts/builder.py` implementava P1/P2/P1L e bloqueava P3/P4. A entrega implementa a base documental e completa as quatro estratégias.

Criar uma base de conhecimento controlada, um recuperador por categoria e a montagem efetiva de P3/P4. A entrega deve gerar **312 prompts** no preflight dos 78 casos × quatro estratégias, registrar a recuperação e proteger a retomada contra mudanças na base.

Essa etapa verifica a preparação do experimento. Gerar prompts não comprova qualidade das correções nem completa a avaliação de segurança ou funcionalidade.

## 2. Escopo e decisões

### Incluído

- Dez documentos Markdown, índice versionado e manifesto de hashes.
- Recuperação por CWE/categoria, sem embeddings ou banco vetorial.
- P3 com alerta SAST e contexto documental; P4 com o mesmo conteúdo e roteiro existente.
- Registro de categoria recuperada, documento, versão, hashes e motivo da seleção.
- Validação da base e do conteúdo incorporado ao prompt.
- Integração com preflight, tentativas e contrato da feature 02.
- Preservação das mensagens e hashes de P1/P2/P1L.

### Fora desta feature

- Chamar a API ou executar correções reais/piloto de remediação.
- Alterar regras SAST, catálogo, identidade, R/M, definição de F ou classificação F/D.
- Criar novos testes de segurança para os casos de frontend.
- Recuperação semântica, múltiplos documentos ranqueados ou feedback automático.
- Alterar as restrições, papel, formato de resposta ou roteiro já congelados.

Usar um documento por tentativa. P1L permanece diagnóstico separado, não quinta estratégia da cadeia.

## 3. Estado do catálogo e cobertura proposta

Distribuição atual de `categoria_rag` no catálogo ampliado:

| Categoria | Casos |
|---|---:|
| generico | 32 |
| broken_access_control | 18 |
| cross_site_scripting | 12 |
| injection | 6 |
| security_misconfiguration | 6 |
| cryptographic_failures | 4 |
| **Total** | **78** |

Os 32 genéricos incluem CWEs de autenticação, validação, integridade, concorrência e NoSQL. Essa categoria foi calculada na feature 01 com o mapa existente; é metadado histórico e deve permanecer intacta.

**Não editar `config/mapa_categoria_rag.yaml`, os demais mapas de origem nem o catálogo para implementar a nova cobertura:** seus hashes são parte da proveniência validada. Introduzir as associações complementares exclusivamente no índice novo. Registrar a diferença entre `categoria_rag` do catálogo e `rag_categoria_recuperada` da tentativa.

## 4. Organização da base

```text
knowledge_base/
├── README.md
├── _index.yaml
├── manifesto.json
├── injection.md
├── broken_access_control.md
├── cryptographic_failures.md
├── cross_site_scripting.md
├── security_misconfiguration.md
├── authentication_failures.md
├── input_validation.md
├── integrity_failures.md
├── concurrency.md
└── generico.md
```

O README explica edição, validação, fontes e congelamento. Ele não vai ao prompt.

### Conteúdo mínimo dos documentos

| Documento | Conteúdo |
|---|---|
| injection | SQL parametrizado, seletores NoSQL, interpretação de código/templates, XXE e concatenação de entradas; explicar limites de cada mitigação |
| broken_access_control | Propriedade e autorização de recursos, papel autenticado, path traversal, SSRF, redirecionamento e mass assignment |
| cryptographic_failures | Segredos embutidos, gestão de chaves, hashing de senhas e usos de algoritmos segundo o contexto |
| cross_site_scripting | Origem não confiável, contexto de saída, escaping, sanitização e APIs Angular que desativam proteção |
| security_misconfiguration | Exposição de dados/arquivos, listagem de diretórios e ReDoS/limites de recursos |
| authentication_failures | Senha atual, credenciais, controles contra tentativas excessivas e preservação do fluxo legítimo |
| input_validation | Tipos, faixas, campos obrigatórios, validação de todas as entradas e invariantes de negócio |
| integrity_failures | Autenticidade e origem de dados/componentes, com distinção entre dado confiável e controlável |
| concurrency | Condições de corrida, atomicidade e invariantes sob requisições concorrentes |
| generico | Avaliação contextual de alertas, origem/fluxo/impacto, mudança mínima e limites do diagnóstico estático |

Cada documento deve explicar mecanismos diferentes em subseções; não recomendar uma mitigação universal para toda a categoria. Por exemplo, parametrização SQL não é uma solução genérica para NoSQL ou execução de código.

## 5. Fontes, autoria e formato dos documentos

Durante a implementação, consultar fontes primárias: OWASP Cheat Sheet Series, documentação CWE e documentação oficial de Node.js, Express, Angular e bibliotecas diretamente tratadas. Registrar URL específica, título e data de consulta; não inventar referências nem copiar grandes trechos.

Não usar os codefixes oficiais, soluções dos desafios, patches das tentativas anteriores, IDs AMP/JS, nomes de desafios ou trechos específicos do Juice Shop como conteúdo da base. Os exemplos devem ser genéricos e pequenos, em JS/TS quando aplicável.

Usar frontmatter YAML:

```yaml
---
schema_versao: '1.0'
categoria: injection
versao_documento: '1.0'
status: PRONTO
fontes:
  - titulo: Título da fonte consultada
    url: https://dominio-oficial/pagina-especifica
    consultado_em: 'AAAA-MM-DD'
---
```

O corpo deve conter, nesta ordem:

1. Descrição e sinais do mecanismo.
2. Origem dos dados e condições para a falha ser real.
3. Impactos e distinção entre padrão suspeito e vulnerabilidade comprovada.
4. Recomendações de mitigação por mecanismo.
5. Cuidados para preservar comportamento funcional.
6. Exemplo genérico vulnerável e corrigido.
7. Limitações e verificações necessárias após a alteração.

`status` aceita `RASCUNHO` e `PRONTO`. Publicação do manifesto e uso de P3/P4 exigem todos os documentos referenciados como PRONTO. Isso é uma validação editorial do artefato, não uma exigência nova de aprovação externa.

Somente o corpo é incorporado ao prompt. Fontes e status ficam nos metadados. Corpo obrigatório, até **20.000 caracteres Unicode**, sem truncamento silencioso. Esse limite permite contexto controlado e não substitui medição de tokens/custos no piloto futuro.

O conteúdo não deve instruir a remoção de uma chamada só para fazer o detector parar. Deve recomendar verificar o fluxo e preservar a função legítima, inclusive quando o alerta for um falso positivo.

## 6. Índice e política de recuperação

Criar `src/pipeline/rag/retriever.py`. Sua leitura não acessa rede nem escreve arquivos.

Contrato de `_index.yaml`:

```yaml
schema_versao: '1.0'
base_versao: '1.0'
fallback: generico
documentos:
  injection: injection.md
  broken_access_control: broken_access_control.md
  cryptographic_failures: cryptographic_failures.md
  cross_site_scripting: cross_site_scripting.md
  security_misconfiguration: security_misconfiguration.md
  authentication_failures: authentication_failures.md
  input_validation: input_validation.md
  integrity_failures: integrity_failures.md
  concurrency: concurrency.md
  generico: generico.md
cwe:
  CWE-89: injection
  CWE-78: injection
  CWE-94: injection
  CWE-95: injection
  CWE-943: injection
  CWE-611: injection
  CWE-134: injection
  CWE-79: cross_site_scripting
  CWE-639: broken_access_control
  CWE-22: broken_access_control
  CWE-73: broken_access_control
  CWE-601: broken_access_control
  CWE-918: broken_access_control
  CWE-915: broken_access_control
  CWE-807: broken_access_control
  CWE-327: cryptographic_failures
  CWE-330: cryptographic_failures
  CWE-798: cryptographic_failures
  CWE-321: cryptographic_failures
  CWE-916: cryptographic_failures
  CWE-548: security_misconfiguration
  CWE-200: security_misconfiguration
  CWE-1333: security_misconfiguration
  CWE-502: security_misconfiguration
  CWE-620: authentication_failures
  CWE-522: authentication_failures
  CWE-307: authentication_failures
  CWE-862: broken_access_control
  CWE-863: broken_access_control
  CWE-20: input_validation
  CWE-841: input_validation
  CWE-345: integrity_failures
  CWE-1357: integrity_failures
  CWE-353: integrity_failures
  CWE-829: integrity_failures
  CWE-362: concurrency
```

As associações são operacionais para contextualização, não reclassificam OWASP nem constituem ground truth. Revisar o conteúdo técnico durante a autoria e registrar qualquer alteração do índice antes de publicar a versão inicial.

### Recuperação determinística

1. Obter `cwe_ids` quando disponíveis; nos casos históricos, extrair `CWE-N` da lista `cwe`.
2. Percorrer IDs na ordem registrada e selecionar a primeira CWE mapeada no índice.
3. Se nenhuma corresponder, usar `categoria_rag` do catálogo quando declarada em `documentos`.
4. Caso contrário, selecionar `fallback=generico`.

Não consultar justificativa/classificação da auditoria, respostas anteriores, resultado R/F/M ou nome do desafio para selecionar documentos.

Retornar categoria, caminho relativo à raiz do repositório, versão, corpo, hash do arquivo completo, hash do corpo, hash do índice e motivo: `cwe`, `categoria_catalogo` ou `fallback`. Registrar a CWE que decidiu a recuperação quando houver.

Arquivo indexado ausente, vazio, malformado ou fora da base é erro. Não usar fallback para esconder corrupção de um documento conhecido. Rejeitar caminho absoluto, `..`, symlink que saia da base, YAML com chaves duplicadas, schema desconhecido e categorias referenciadas sem documento.

## 7. Manifesto e congelamento documental

Criar `scripts/experiment/validate_knowledge_base.py`:

```bash
# Somente leitura: valida conteúdo e confere o manifesto existente.
python scripts/experiment/validate_knowledge_base.py

# Após autoria/revisão: publica manifesto se ainda não existe.
python scripts/experiment/validate_knowledge_base.py --publicar-manifesto
```

Adicionar `--base` opcional, com padrão `knowledge_base/` ancorado no repositório. Argumentos relativos explícitos são resolvidos contra o diretório corrente. Não sobrescrever um manifesto existente. Nova edição requer versão declarada nova e arquivamento explícito da versão anterior; não oferecer `--force`.

`manifesto.json` deve conter schema/base_versao, hash do índice, hashes dos dez arquivos completos e dos corpos, versões, categorias e fontes declaradas. Não incluir timestamp de execução, duração nem caminhos absolutos. Serialização JSON UTF-8, ordenada, indentada e com newline final.

O manifesto não inclui auto-hash nem hash do README. `hash_base` é o SHA-256 dos bytes exatos do manifesto; a consistência do índice/documentos é validada antes de utilizá-lo. As datas de consulta pertencem ao frontmatter e influenciam o hash do arquivo.

Validar por leitura os dez documentos antes de publicar. O comando padrão exige manifesto presente e consistente; divergências são erro, não motivo para regeneração automática.

## 8. Montagem de prompts

Manter `PAPEL`, `RESTRICOES`, `FORMATO`, roteiro, seleção de código e política de janela atuais. Não alterar mensagens de P1/P2/P1L nem a fórmula existente de `hash_prompt`.

| Estratégia | Blocos do usuário, em ordem |
|---|---|
| P1 | Tarefa → código → restrições → formato |
| P2 | Tarefa → código → roteiro → restrições → formato |
| P1L | Tarefa → código → alerta atual → restrições → formato |
| P3 | Tarefa → código → mesmo bloco de alerta atual → contexto documental → restrições → formato |
| P4 | Tarefa → código → mesmo bloco de alerta atual → contexto documental → roteiro → restrições → formato |

Usar o `bloco_alerta` existente, sem acrescentar classificação da auditoria. O contexto tem cabeçalho fixo:

```text
Contexto técnico recuperado para apoiar a análise:
<corpo do documento>
```

P3/P4 do mesmo caso devem recuperar o mesmo corpo; a diferença é o roteiro. Documentos não devem fazer referência ao processo experimental ou pedir saída incompatível com o schema comum.

`verificar_disponivel` deve validar a base completa para P3/P4 e o roteiro para P2/P4. P1/P2/P1L devem funcionar quando a base estiver ausente, sem exigir seu manifesto.

O retriever não altera `issue`. P3/P4 recebem contexto suplementar; os dados originais do catálogo permanecem preservados.

## 9. Metadados e integração

Estender `PromptMontado` com campos opcionais, usando `null`/`false` em estratégias sem RAG:

- `rag_categoria_recuperada`, `rag_motivo_recuperacao`, `rag_cwe_selecionada`.
- `rag_documento_versao`, `rag_documento_sha256`, `rag_corpo_sha256`.
- `rag_index_sha256`, `rag_base_sha256`.

Preencher `usa_rag=true` e `arquivo_rag_recuperado` em P3/P4. Conservar `usa_rag=false` e caminho nulo nas demais. Os novos campos não entram em `mensagens`; o hash do prompt continua refletindo o texto efetivamente enviado.

Propagar os metadados de recuperação ao registro da tentativa e ao relatório do preflight. Não expor caminhos absolutos da máquina nem incorporar status/fontes/classificação ao texto de P1/P2.

### Contrato de retomada

Se alguma estratégia solicitada usar RAG, adicionar ao contrato hashes do manifesto, índice e documentos da base publicada. Não incluir timestamps. Mudança em qualquer um desses artefatos impede retomada na mesma saída.

Novas execuções, inclusive sem RAG, usam contrato 2.0. Saídas antigas com apenas P1/P2/P1L mantêm o contrato 1.0 e seus bytes; adicionar a base não deve invalidar uma retomada que não usa RAG quando a equivalência textual estiver comprovada.

O contrato atual também guarda o hash de `builder.py`, cuja alteração nesta feature mudaria contratos antigos mesmo sem mudar mensagens. Tratar isso por compatibilidade explícita:

- Novas execuções usam uma versão de contrato nova com hashes dos componentes textuais relevantes, em vez do arquivo inteiro do builder.
- Para uma saída antiga, só permitir retomada se a projeção das mensagens solicitadas, roteiro e restrições tiver hashes iguais aos prompts originais concluídos/preflight e os demais campos científicos coincidirem.
- Não sobrescrever contratos da feature 02 para migrá-los. Validar o contrato antigo em modo de leitura e manter sua identidade nos registros retomados.
- Para saída antiga sem evidência suficiente para comprovar equivalência, exigir uma execução nova.

Implementar essa compatibilidade somente para estratégias sem RAG; saídas antigas não podem passar a incorporar P3/P4.

Revalidar hashes antes de cada montagem/tentativa. Não continuar uma execução com base modificada entre casos.

## 10. Validação sem API

### Regressão de P1/P2/P1L

Antes de editar o builder, guardar hashes e mensagens dos casos selecionados com o código atual. Usar também os 156 prompts arquivados da feature 02 como referência de P1/P2 dos 78 casos.

Após implementar, comparar `mensagens` e `hash_prompt` byte a byte para os mesmos dados. Campos adicionais de metadados podem existir no JSON; não exigir identidade de todo o arquivo de prompt.

### Preflight das quatro estratégias

```bash
PYTHONPATH=src .venv/bin/python -m pipeline.run_pipeline \
  --execucao AMP_RAG_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/feature03/AMP_RAG_PREFLIGHT_01 \
  --estrategias P1,P2,P3,P4 --somente-preflight --k 1 \
  --semgrep-bin .venv/bin/semgrep
```

Conferir 78 casos × quatro estratégias = **312 prompts**, com 156 recuperações P3/P4. Não aplicar regra de parada por aceite ao preflight: não existe tentativa de correção nesse modo.

Produzir relatório de cobertura por categoria original/recuperada, CWE selecionada, fallback e tamanhos dos corpos/prompts. A contagem de fallback após o índice complementar deve ser medida; não alterar o índice para atingir artificialmente uma meta de zero.

Inspecionar manualmente uma amostra de cada categoria, incluindo falsos positivos, casos sem OWASP, um caso com múltiplas CWEs e o fallback com fixture sintética. Verificar que contexto inadequado ou genérico é registrado, não apresentado como diagnóstico conclusivo.

Preflight real depende do perfil e checkout preparados nas features anteriores. Se não estiverem disponíveis, concluir testes isolados e registrar a geração real como pendente.

## 11. Testes obrigatórios

- [x] P1/P2 dos 78 casos mantêm mensagens/hash dos artefatos da feature 02; P1L mantém a referência capturada antes da mudança.
- [x] P3 inclui código, alerta e corpo correto; P4 acrescenta somente o roteiro.
- [x] P3/P4 do mesmo caso têm documentos e hashes iguais.
- [x] Recuperação por primeira CWE mapeada, categoria do catálogo e fallback, com motivos distintos.
- [x] Casos históricos sem `cwe_ids` são suportados.
- [x] Nenhuma classificação da auditoria influencia recuperação ou aparece no prompt.
- [x] A recuperação não altera o catálogo/issue recebido.
- [x] Base ausente não quebra P1/P2/P1L; impede P3/P4.
- [x] Índice inválido, chaves duplicadas, documento ausente/vazio, schema/status inválido e corpo acima do limite falham.
- [x] Caminhos externos, `..` e symlink fora da base são recusados.
- [x] Hash de documento/índice/manifesto alterado impede montagem e retomada RAG.
- [x] Arquivos alterados entre publicação e montagem são detectados.
- [x] Manifesto determinístico; publicação recusa destino existente.
- [x] Fontes obrigatórias, categorias e versões do frontmatter são validadas.
- [x] Preflight das quatro estratégias não instancia cliente LLM, aplica patch ou roda testes funcionais.
- [x] Contratos novos e compatibilidade de contratos antigos sem RAG são testados com prompts equivalentes e divergentes.

Usar fixtures pequenas para erros e recuperação. Não realizar consultas web nem chamadas à API nos testes automatizados. Consultas às fontes ocorrem somente durante a autoria dos documentos.

## 12. Arquivos de implementação

- `knowledge_base/`: documentos, índice, manifesto e instruções de manutenção.
- `src/pipeline/rag/retriever.py`: carregamento, validação e seleção.
- `scripts/experiment/validate_knowledge_base.py`: comando editorial de validação/publicação.
- Builder, orquestrador e contrato: montagem, proveniência e compatibilidade de retomada.
- `tests/unit/test_rag_prompts.py`: recuperação, regressão, erros e contratos.
- Protocolo, README e guia: atualizar estado e instruções após validação.

Não reutilizar os contextos Python da PoC como se fossem documentos prontos para o Juice Shop; usar sua estrutura como referência e escrever conteúdo adequado a JS/TS/Angular.

## 13. Critérios de aceite

- [x] Dez documentos completos, tecnicamente revisados e com fontes primárias verificadas.
- [x] Índice e manifesto consistentes, versionados e reproduzíveis.
- [x] P3/P4 implementados, sem mudança nas mensagens de P1/P2/P1L.
- [x] Recuperação e hashes presentes nos prompts, registros e contrato.
- [x] Testes novos e `make test-unit` passando.
- [x] Preflight real de 312 prompts concluído e inspecionado.
- [x] Nenhum artefato de features 01/02 ou fonte congelada alterado.
- [x] Zero chamadas à API e checkout limpo ao final.
- [x] `ENTREGA.md` registra categorias recuperadas, fallbacks, fontes, hashes, comandos e limites.

Não aceitar como conclusão apenas criar `_index.yaml`, remover a exceção de P3/P4 ou repetir um contexto genérico sem registrar a seleção.

## 14. Limitações e continuação

P3/P4 acrescentam diagnóstico SAST e documento ao mesmo tempo. Uma eventual melhora não deve ser atribuída exclusivamente ao RAG sem considerar esse fator; P1L é um diagnóstico adicional existente, não um controle automaticamente suficiente para todas as conclusões.

A base é elaborada após conhecimento das categorias do alvo e deve ser descrita como contextualização controlada. Evitar exemplos que reproduzam soluções dos casos. Recuperação por categoria não garante que o documento seja específico para a causa real do alerta.

Após o aceite, realizar um piloto com chamadas reais em poucos casos, com orçamento e templates congelados. A validação funcional dos casos de frontend e o tratamento dos testes dependentes de linha/vulnerabilidade precisam estar resolvidos ou explicitamente delimitados antes das conclusões do experimento final.

## 15. Evidência medida

115 testes passaram. O preflight gerou 312 prompts e 156 recuperações, todas por CWE. Os 21 falsos positivos e 49 casos sem OWASP permaneceram incluídos. Não há múltiplas CWEs no catálogo oficial; ordem e fallback foram validados com fixtures sintéticas. A limitação do documento amplo para CWE-915 está registrada na [cobertura](../../../../outputs/feature03/cobertura_rag.json).
