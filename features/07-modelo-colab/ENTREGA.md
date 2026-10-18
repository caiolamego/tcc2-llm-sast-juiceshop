# Entrega — Feature 07: Qwen no Colab

Data: 17/10/2026. **Implementação e aceite offline concluídos. Conexão Colab, compatibilidade na GPU e piloto real pendentes**, conforme o escopo autorizado. Nenhuma geração externa, download de pesos, instalação, commit ou push foi feito nesta entrega.

## O que foi entregue

- Fábrica comum selecionada por `LLM_PROVIDER`, mantendo OpenAI como padrão e suas classes, cache, preços e orçamento anteriores.
- Cliente Colab com autenticação, identidade verificada em `/health` e `/v1/models`, header `X-LLM-Identity`, schema real `Correcao`, limite 4096, timeout 600 s e uma inferência simultânea independente de K.
- Manifesto do notebook com revisão imutável, tokenizer, template, quantização, dtype, versões, código efetivo do servidor e ambiente. Células e servidor foram compilados estaticamente; não executados.
- Cache Colab isolado e verificado por hash, publicação atômica, contador persistente próprio com reservas seguras entre processos. Cada envio/reenvio conta; timeout não devolve reserva. Somente 429 é repetido, até três envios.
- Resposta truncada/recusada/inválida sem patch aplicado. Erros operacionais encerram a fila e são registrados separadamente, sem inventar F=0 ou tentativa concluída.
- Contrato 5.0 nas novas execuções ampliadas, preservando contexto de validação 3.0/4.0. Leitores históricos mantidos; contratos antigos não são migrados. Mudança de URL/token exige mesma identidade científica; modelos diferentes requerem saídas diferentes.
- Provedor/identidade, tempos de espera/requisição, custos desconhecidos e cache em registros, painel e métricas. Acrescentado `metricas_por_inferencia.csv` somente para a versão nova.
- Diagnóstico explícito offline/conexão/smoke; o smoke usa schema real e contador próprio. Notebook local de diagnóstico atualizado, sem URL temporária fixa ou saídas salvas.
- Credenciais herdadas do shell são removidas do ambiente de subprocessos SAST e testes. `.env` pessoal e `config/execucao.yaml` foram preservados integralmente.

## Evidências

Arquivadas em [VALIDACAO_OFFLINE_V1](../../outputs/feature07/VALIDACAO_OFFLINE_V1/):

| Verificação | Resultado |
|---|---|
| Testes antes | 266 passaram, 17,055 s |
| Testes depois | 302 passaram, 20,774 s; 36 novos |
| HTTP local | SDK e schema reais com servidor sintético local; nenhuma GPU ou API externa |
| Falhas | 401/429/5xx, modelo/identidade divergentes, timeout, desconexão e resposta inválida cobertos |
| Concorrência | Reservas testadas com threads e processos; limite persistente respeitado |
| Integridade | 4.060 arquivos protegidos conferidos, zero alterações |
| Checkouts | `catalogo-alvo` e `wt-1` a `wt-4` limpos no commit fixado |
| Notebooks | Células Python e fonte incorporada do servidor com sintaxe válida, sem execução |
| Frontend | `node --check frontend/painel/app.js` aprovado |
| Requisitos | Linhas de `requirements.txt` analisadas com parser de requisitos |
| Git | `git diff --check` aprovado |

Commit do alvo: `f915bddd82790d0f3018902d36ae9b4241a5f51f`.

Ambiente local: Python 3.12.3, OpenAI SDK 3.29.0, httpx 0.28.1, Pydantic 2.14.1 e python-dotenv 1.2.4. As versões fixadas do notebook foram preservadas; o ambiente GPU ainda não foi exercitado nesta entrega. Não há alegação de equivalência entre o SDK local e uma execução efetiva no Colab.

O relatório [verificacao.json](../../outputs/feature07/VALIDACAO_OFFLINE_V1/verificacao.json) contém hashes e resultados. [manifesto.json](../../outputs/feature07/VALIDACAO_OFFLINE_V1/manifesto.json) identifica os artefatos e fontes desta entrega. O inventário público de entradas protegidas omite o hash do `.env` pessoal; sua preservação foi conferida no snapshot privado local.

## Comandos

```bash
make test-unit PYTHON=.venv/bin/python
node --check frontend/painel/app.js
git diff --check
```

Para usar o Colab manualmente, siga [docs/modelo_colab.md](../../docs/modelo_colab.md). Depois de iniciar o notebook e preencher `.env`/manifesto:

```bash
.venv/bin/python scripts/experiment/diagnose_llm.py --modo offline
.venv/bin/python scripts/experiment/diagnose_llm.py --modo conexao
.venv/bin/python scripts/experiment/diagnose_llm.py --modo smoke
.venv/bin/python painel.py
```

Os três últimos comandos acima não foram executados contra o Colab nesta entrega. Para conferir `--help`, não é necessário servidor ou chave.

## Pendências e limites

- [ ] Iniciar o runtime GPU, verificar memória e versões efetivas e exportar o manifesto novo.
- [ ] Preencher token e URL privados no `.env`; não usar a chave OpenAI como token do Colab.
- [ ] Validar autenticação, identidade e schema real pelo túnel.
- [ ] Conferir se os prompts P1–P4 cabem em 8192 tokens totais com a saída reservada; não houve tokenização real com o Qwen nesta entrega.
- [ ] Executar piloto manual em saída nova, preferencialmente login/keyServer antes de ampliar a coleta.
- [ ] Avaliar latência, disponibilidade, patches aplicáveis e R/F/M medidos. Nenhum ganho de desempenho ou eficácia foi presumido.

A configuração padrão permanece OpenAI, 10 issues e K=4. Uma inferência Colab por vez não exige reduzir K. Testes de API continuam serializados. O aceite histórico e os resultados anteriores não foram recalculados ou substituídos.

Retomadas OpenAI antigas continuam pelo caminho anterior e exigem compatibilidade científica; mudanças de implementação relevantes podem exigir nova saída, como antes. Uma execução antiga não recebe o provedor Colab retrospectivamente. O painel precisa ser reiniciado manualmente para carregar o código novo; não foi reiniciado automaticamente.
