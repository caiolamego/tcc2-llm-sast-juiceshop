# Executar o pipeline com Qwen no Colab

A feature 07 permite escolher OpenAI ou o servidor Qwen do notebook. A implementação foi validada offline; o funcionamento na GPU e o piloto ainda precisam ser conferidos manualmente. Catálogo, prompts, SAST, testes e critérios R/F/M continuam os mesmos.

## Preparar o notebook

1. Abra [qwen_colab_api.ipynb](../../notebooks/qwen_colab_api.ipynb) no Colab com GPU. Ele usa Qwen2.5-Coder-14B-Instruct em NF4; não troca automaticamente para 7B.
2. Confira a disponibilidade de memória e execute as células em ordem. Forneça `COLAB_LLM_API_KEY` e `NGROK_AUTHTOKEN` pela entrada oculta ou secrets. O primeiro é uma senha escolhida para a API; o segundo pertence à sua conta ngrok. Nenhum deles é uma chave OpenAI.
3. Após definir o servidor, baixe `manifesto_colab.json` e copie para `config/modelos/manifesto_colab.json` nesta máquina. O manifesto contém revisões, tokenizer, template, versões e identidade; não contém credenciais. Não use um manifesto fictício.
4. Anote a URL HTTPS terminada em `/v1`. Em reproduções, fixe `MODEL_REVISION` no SHA exportado e confira a identidade novamente. A GPU e o runtime podem variar; seed não garante reprodução bit a bit.

A sessão precisa permanecer disponível. A integração não contorna limites do Colab; confira as [condições e limites oficiais](https://research.google.com/colaboratory/faq.html) para seu plano. O túnel ngrok transporta as mensagens e respostas. Não há servidor permanente pressuposto.

## Configurar localmente

Na raiz do projeto, edite seu `.env` com os campos de [`.env.example`](../../.env.example):

```dotenv
LLM_PROVIDER=colab
COLAB_BASE_URL=https://<endereco-exibido-no-notebook>/v1
COLAB_API_KEY=<mesma-senha-do-secret-COLAB_LLM_API_KEY>
COLAB_MODEL=Qwen/Qwen2.5-Coder-14B-Instruct
COLAB_MODEL_MANIFEST=config/modelos/manifesto_colab.json
COLAB_SEED=42
COLAB_TIMEOUT_S=600
COLAB_MAX_OUTPUT_TOKENS=4096
COLAB_MAX_IN_FLIGHT=1
```

Substitua os placeholders. Nunca versione `.env` ou salve tokens nas células/saídas do notebook. Variáveis exportadas no terminal prevalecem sobre `.env`; se a configuração parecer diferente, confira as exportações sem imprimir segredos.

`MAX_LLM_CALLS` limita os envios Colab acumulados em `.cache/colab/orcamento.json`, inclusive reenvios e diagnósticos de geração. Não é um limite por execução. Cache não consome outra chamada. Não apague o contador para esconder consumo; aumente o limite conscientemente quando necessário.

OpenAI mantém `.cache/orcamento_llm.json` e seu cache original. `MAX_USD` protege OpenAI, não a infraestrutura Colab. Os custos Colab desconhecidos são exportados como `null`, sem assumir gratuidade.

## Conferir antes de iniciar

Ative a `.venv`, ou use seu Python diretamente:

```bash
.venv/bin/python scripts/experimento/diagnosticar_llm.py --modo offline
.venv/bin/python scripts/experimento/diagnosticar_llm.py --modo conexao
.venv/bin/python scripts/experimento/diagnosticar_llm.py --modo smoke
```

- `offline`: valida configuração e manifesto, sem rede.
- `conexao`: autentica em `/health` e `/v1/models`, confere modelo/identidade, sem geração.
- `smoke`: gera um objeto sintético com o schema real `Correcao`; consome chamada quando não há cache. Não altera o Juice Shop nem é tentativa do experimento. A saída indica quantos envios ocorreram e se houve cache.

Também há um [notebook de diagnóstico local](../../notebooks/teste-local.ipynb), usando esses mesmos comandos. Nenhum comando de diagnóstico chama OpenAI automaticamente. Um diagnóstico mal sucedido retorna código 1, argumentos inválidos retornam 2 e sucesso retorna 0.

O preflight científico continua sem consulta ao Colab ou geração LLM. Antes das tentativas reais, a identidade remota será verificada. Essa separação permite preparar tudo offline sem declarar conectividade comprovada.

## Enviar uma mensagem simples pelo código local

Para enviar somente `teste` do computador para a API Colab configurada no `.env`, usando o mesmo cliente de geração do pipeline:

```bash
.venv/bin/python scripts/experimento/diagnosticar_llm.py --modo mensagem --mensagem "teste"
```

A resposta aparece no terminal e é arquivada numa pasta nova em `outputs/diagnosticos_llm/`. O cliente mantém autenticação, modelo, parâmetros e schema JSON `Correcao` do pipeline; somente a mensagem enviada é `teste`. Portanto a resposta continua estruturada em JSON. Não usa worktrees, não aplica patches, não executa SAST ou testes. Conta como chamada Colab quando não houver cache e atravessa a URL configurada (incluindo ngrok, se for o endpoint atual). Este teste não equivale ao teste HTTP local dentro do Colab.

## Enviar somente um prompt arquivado

Para isolar a LLM do restante do pipeline, envie o P1 original da issue `keyServer.ts` que falhou:

```bash
.venv/bin/python scripts/experimento/diagnosticar_llm.py --modo prompt \
  --prompt-arquivo outputs/piloto_colab_1_issue/AMP_REAL_20261017T222912Z_abd18103/prompts/*.json
```

O glob acima deve corresponder a um único arquivo. O comando confere o hash do builder e envia as mensagens sem alterações, com o schema e os parâmetros Colab atuais. Não prepara worktrees, não aplica edições, não chama Semgrep nem testes funcionais. É um diagnóstico, separado das tentativas do experimento, e consome o limite Colab quando não há cache.

Cria uma pasta nova em `outputs/diagnosticos_llm/`, com `prompt.json`, `resultado.json` e, quando houver retorno da geração, `resposta.json`. Erros conhecidos do servidor/túnel aparecem em `resultado.json`; nenhum reenvio adicional é feito além da política existente de 429. `--saida` permite escolher um destino novo, sem sobrescrita. Os resultados históricos são preservados.

## Iniciar pelo painel

```bash
.venv/bin/python painel.py
```

Se o painel já estiver aberto em outro processo, encerre esse processo pelo terminal que o iniciou antes de reiniciar; atualize a página após o reinício. Confira provedor e modelo na tela e use **Real → Iniciar pipeline**. Alternativa pelo terminal:

```bash
.venv/bin/python executar.py
```

A configuração atual usa **10 issues e K=4**. `wt-5` e `wt-6` permanecem preparadas no disco para uso futuro. Esta entrega não a troca por outro piloto. Para começar com duas, selecione explicitamente em `config/execucao.yaml` somente `AMPfb154534099cb3ca` (login) e `AMP95adf572d3c6677f` (keyServer), mantendo P1–P4, e use uma execução nova. Não reutilize a saída de um piloto OpenAI.

K=4 permite até quatro issues em processamento local. `COLAB_MAX_IN_FLIGHT=1` limita a GPU a uma geração por vez; outras worktrees podem executar compilação, SAST e testes. A serialização de testes de API permanece vigente.

## Falhas, retomada e evidências

- A requisição leva `X-LLM-Identity`; o servidor recusa identidade divergente antes de gerar.
- Contexto de 8192 inclui entrada e saída. Não há truncamento automático. Se faltar espaço ou VRAM, planeje nova configuração e execução, sem reduzir os prompts silenciosamente.
- Somente 429 de GPU ocupada é repetido: até três envios, espera de no máximo 30 s por reenvio. Outros erros HTTP, desconexão e timeout interrompem a fila. Uma reserva após timeout permanece consumida, pois o resultado remoto pode ser desconhecido.
- Parar pelo painel cancela a fila local. Uma requisição já enviada pode continuar no Colab até terminar; encerramento da sessão remota é feito no notebook.
- Respostas brutas ficam arquivadas; resposta truncada, recusada ou inválida não é aplicada. Falha de transporte não vira F=0 nem tentativa de correção concluída.
- Novas execuções ampliadas usam contrato 5.0 com identidade da inferência e contexto de validação. Manifesto alterado, outro modelo, parâmetros ou implementação incompatíveis impedem retomada. Contratos antigos não são migrados; o caminho OpenAI anterior permanece sujeito às verificações científicas existentes.
- URL e token podem mudar numa reconexão, desde que a identidade científica permaneça igual. `llm_operacional.jsonl` registra eventos sem credenciais ou endereço completo; reservas ficam no contador Colab.
- Painel e métricas distinguem modelo/provedor, cache, espera e requisição. As métricas 5.0 acrescentam `metricas_por_inferencia.csv` e preservam agrupamento funcional quando aplicável.

Voltar ao OpenAI exige `LLM_PROVIDER=openai` e uma saída compatível com esse provedor. Indisponibilidade Colab não provoca fallback ou cobrança OpenAI.
