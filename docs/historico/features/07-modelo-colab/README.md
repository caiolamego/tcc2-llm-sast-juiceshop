# Feature 07 — Modelo hospedado no Colab

Status: implementada com validação offline. Conectividade Colab, schema na GPU e piloto real permanecem pendentes. Consulte a [entrega](ENTREGA.md) e o [procedimento manual](../../../guias/modelo_colab.md).

## Objetivo

Permitir selecionar OpenAI ou um modelo de pesos abertos executado no Colab, pelo terminal e painel, mantendo catálogo, prompts P1–P4, RAG, validação funcional, SAST e critérios R/F/M. O Juice Shop, worktrees e testes continuam nesta máquina; somente as mensagens de inferência são enviadas ao servidor.

Fluxo: painel/lançador → cliente LLM → endpoint HTTPS autenticado → servidor de inferência no Colab → resposta JSON → aplicação e validação locais.

## Diagnóstico anterior à implementação

- `src/pipeline/llm/openai_client.py` concentra configuração, transporte, cache e orçamento. Exige `OPENAI_API_KEY` e preço em `config/precos_llm.yaml`.
- A requisição atual usa Chat Completions, `temperature=0`, seed, JSON Schema estrito e limite de saída de 4096 tokens. A compatibilidade desses parâmetros precisa ser demonstrada no servidor escolhido.
- O cache identifica mensagens/modelo/seed, sem distinguir revisão dos pesos, servidor ou quantização. Essa identidade não é suficiente para o novo provedor.
- O lock de orçamento envolve a chamada inteira: atualmente serializa a inferência mesmo com várias worktrees.
- Os contratos ampliados atuais registram validação e prompts, mas precisam passar a registrar também a identidade científica da inferência.

## Decisões e requisitos externos

1. Usar o notebook existente: Qwen2.5-Coder-14B-Instruct, NF4, Transformers, FastAPI, LM Format Enforcer e ngrok. O cliente usa `/health`, `/v1/models` e `/v1/chat/completions`; não haverá troca automática para outro backend ou modelo.
2. Preservar os parâmetros iniciais do notebook: contexto 8192, saída máxima 4096, seed 42 e geração sequencial. Exportar revisão imutável e ambiente antes do piloto; falta de memória ou contexto exige ajuste explícito em nova condição experimental.
3. A URL deve ser alcançável desta máquina, com HTTPS e autenticação. `localhost` do notebook não aponta para o Colab nesta máquina. O mecanismo de conectividade será definido na preparação do ambiente, respeitando as condições do serviço; não automatizar túnel nesta etapa de planejamento.
4. Nenhum fallback automático para OpenAI: indisponibilidade do Colab não pode gerar cobranças ou misturar modelos.
5. Não alterar mensagens para acomodar o novo modelo silenciosamente. A serialização do chat pelo tokenizer é parte da identidade do modelo. Caso precise mudar texto, criar outra condição experimental.
6. A VM do Colab pode encerrar e a disponibilidade de GPU varia. Retomada deve funcionar após reconexão sem mudar a identidade científica. O uso como servidor externo precisa ser compatível com o plano e as condições do Colab; endpoint permanente não é pressuposto.

## Configuração prevista

Os campos de [`.env.example`](../../../../.env.example) são lidos pelo runtime. OpenAI continua selecionado por padrão; `.env` pessoal e configuração K=4 não foram alterados. A nova integração não fez chamadas reais durante a entrega.

| Campo | Preenchimento e regra |
|---|---|
| `LLM_PROVIDER` | `openai` por padrão; `colab` seleciona exclusivamente o endpoint configurado. |
| `COLAB_BASE_URL` | URL HTTPS terminada em `/v1`, sem usuário, senha ou token na URL. |
| `COLAB_API_KEY` | Token privado do servidor de inferência. Não reutilizar `OPENAI_API_KEY`. |
| `COLAB_MODEL` | Identificador exato retornado pelo servidor. |
| `COLAB_MODEL_MANIFEST` | Caminho do manifesto de identidade, sem credenciais. |
| `COLAB_SEED` | Inteiro; registrar suporte efetivo, sem prometer determinismo entre GPUs. |
| `COLAB_TIMEOUT_S` | Timeout positivo de requisição; padrão 600 s. |
| `COLAB_MAX_OUTPUT_TOKENS` | Inteiro positivo; padrão 4096, limitado pelo modelo. |
| `COLAB_MAX_IN_FLIGHT` | Nesta versão, somente 1; independente de K. |
| `MAX_LLM_CALLS` | Limite de chamadas preservado, com reservas seguras entre workers. |
| `MAX_USD` | Proteção das cobranças OpenAI; não equivale a orçamento de GPU Colab. |

Variáveis exportadas no shell prevalecerão sobre `.env`. Validar placeholders, tipos e campos obrigatórios do provedor selecionado. Não exigir chave OpenAI em modo Colab. Nunca injetar tokens em subprocessos do alvo, logs ou painel.

O manifesto deverá declarar: ID e revisão imutável dos pesos, tokenizer e revisão, quantização/dtype, hash do chat template, janela de contexto, backend e versão, capacidades JSON Schema/seed/parâmetros e configuração de geração efetiva. Registrar GPU e dependências como ambiente observado. O manifesto deve ser reconciliado com a configuração real do servidor: `/models` sozinho não comprova revisão ou quantização.

## Etapas de implementação

### 1. Separar provedores e configuração

- [x] Criar configuração e fábrica comuns em `src/pipeline/llm/`, preservando as interfaces públicas do cliente existente.
- [x] Manter o comportamento OpenAI como padrão e adicionar adaptador Colab com URL explícita.
- [x] Usar o schema `Correcao` existente; validar localmente o JSON recebido antes de aplicar qualquer edição.
- [ ] Provar suporte ao schema estrito no backend escolhido na GPU real. Sem suporte, bloquear essa configuração, sem remover restrições silenciosamente.
- [x] Tratar truncamento, recusa, JSON inválido, falta de contexto e desconexão como eventos distintos. Não interpretar falha de transporte como patch rejeitado por segurança ou F=0.
- [x] Preservar os metadados opcionais ausentes do servidor como ausentes; não inventar fingerprint ou tokens.

### 2. Cache, orçamento e contrato científico

- [x] Isolar o cache Colab por provedor, identidade imutável do modelo, mensagens, schema e geração efetiva. Preservar o cache OpenAI histórico.
- [x] Criar versão nova do contrato incluindo identidade de inferência e política de transporte/repetição; manter leitura histórica sem reescrever contratos anteriores.
- [x] Recusar retomada com mudança de modelo, revisão, template, quantização ou parâmetros. Não autorizar acrescentar Colab em execução OpenAI existente.
- [x] Permitir troca de URL/token após reconexão somente comprovando a mesma identidade; registrar a troca como evento operacional, sem publicar segredos.
- [x] Separar custo de API, custo de infraestrutura e disponibilidade desses dados. API sem tarifa por token não implica GPU gratuita. Custo desconhecido permanece `null`, com motivo.
- [x] Reservar chamadas de forma atômica antes do envio; não manter lock global de orçamento durante toda a inferência. Usar semáforo próprio com `COLAB_MAX_IN_FLIGHT`.
- [x] Registrar reenvios e consumo possivelmente desconhecido após timeout. Repetir somente falhas transitórias com limite/backoff; não repetir 401, modelo inexistente ou schema incompatível como falhas transitórias.

### 3. Diagnóstico, painel e métricas

- [x] Propagar seleção pelo lançador, orquestrador e ferramentas auxiliares, usando uma fábrica comum.
- [x] Exibir provedor/modelo/estado no painel sem URL privada completa ou chave.
- [x] Manter preflight científico sem geração LLM. Adicionar diagnóstico explícito separado de conectividade/autenticação/listagem, com timeout curto e sem gerar correção.
- [x] Disponibilizar smoke test de geração explícito, contado no limite de chamadas e separado das tentativas do experimento.
- [x] Medir espera de inferência, duração da requisição, cache e falhas de conexão. Manter tempos de SAST/testes separados.
- [x] Agrupar resultados por identidade do modelo/provedor; não misturar amostras OpenAI e Colab nem cache com nova geração.

### 4. Preparação do Colab e validação manual pendente

- [x] Documentar notebook reproduzível com versões fixadas, obtenção dos pesos/tokenizer, configuração do servidor e manifesto efetivo.
- [ ] Confirmar o modelo, GPU, memória e limite de contexto. Verificar os prompts reais P1–P4; não truncar código ou contexto RAG silenciosamente.
- [ ] Configurar token do servidor nos segredos do notebook e localmente no `.env`, sem versioná-lo (procedimento entregue; configuração pessoal preservada).
- [ ] Conferir `/models` e executar uma chamada sintética com o schema de correção, sem tocar no Juice Shop.
- [ ] Executar novo piloto de duas issues com P1–P4 em saída nova, após solicitação de execução; não sobrescrever pilotos anteriores.
- [ ] Comparar taxa de JSON válido, patches aplicáveis, R/F/M, latência e tokens. Avaliar desempenho medido, sem presumir superioridade ou equivalência ao modelo atual.

## Testes e aceite

Testes automatizados usarão servidor HTTP falso ou mocks, sem Colab, OpenAI, Semgrep ou testes do alvo:

- [x] Configuração de ambos os provedores, precedência do ambiente, validação e não vazamento de credenciais.
- [x] Autenticação, URL `/v1`, modelo incorreto, 401/429/5xx, timeout, reconexão e limite de chamadas concorrentes.
- [x] Schema válido/inválido, truncamento, recusa, campos opcionais e usage ausente.
- [x] Cache isolado entre provedores/revisões, retomadas compatíveis e incompatíveis e mudanças operacionais de URL.
- [x] Regressão textual dos prompts e compatibilidade das métricas históricas.
- [x] Painel e lançador selecionam o mesmo provedor; dry-run/preflight não instanciam cliente de geração.
- [x] `make test-unit` e `git diff --check` aprovados, artefatos históricos preservados.

Aceite desta entrega: implementação, testes offline e comandos manuais. Validação real completa exige servidor/manifesto compatíveis, resposta estruturada real comprovada e piloto arquivado em saída nova; permanece pendente, sem declarar equivalência na GPU.

## Fontes primárias consultadas

- [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct): modelo e tokenizer do notebook.
- [LM Format Enforcer](https://github.com/noamgat/lm-format-enforcer): decodificação restringida por schema, com validação local adicional no pipeline.
- [Google Colab — FAQ](https://research.google.com/colaboratory/faq.html): recursos variáveis, encerramento de sessões e restrições de uso de runtimes gerenciados.

Consulta: 17/10/2026. Modelo e servidor seguem o notebook existente. A conectividade e a viabilidade efetiva na GPU serão verificadas manualmente.

## Decisões finais da implementação

- Contrato 5.0 para novas execuções ampliadas; preserva o contexto de validação 3.0/4.0. Leitores continuam aceitando 1.0–4.0; retomadas antigas OpenAI usam o caminho anterior e continuam sujeitas à integridade científica.
- Contador Colab separado e persistente em `.cache/colab/orcamento.json`; cada envio reserva uma chamada, incluindo reenvios. OpenAI mantém cache e orçamento anteriores.
- Repetir somente HTTP 429, até três envios; `Retry-After` limitado a 30 s. Timeout, desconexão e outros erros HTTP não são reenviados.
- Truncamento/recusa/JSON inválido resultam em geração sem patch aplicável; erros operacionais interrompem a fila e não fabricam tentativa concluída.
- Manifesto e implementação são revalidados durante o uso. Troca de URL/token não muda identidade científica; o hash do endpoint e ambiente observado são registrados como proveniência operacional.
- Os testes offline não baixam pesos, iniciam ngrok, usam GPU, executam Semgrep ou testes do alvo.
