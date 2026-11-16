# Entrega — Feature 09: tolerância a falhas da LLM

**Data:** 02/11/2026.  
**Status:** implementação e validação offline concluídas. Nenhuma chamada real à LLM nesta validação.

## Problema resolvido

O pipeline reutilizava respostas locais da LLM automaticamente. Quando a API falhava,
a execução podia interromper os casos seguintes e deixar de calcular as métricas.
Isso também acontecia no painel web, que supervisiona os processos diretamente.

O piloto Colab `AMP_REAL_20261017T222912Z_abd18103` exemplificava o problema: terminou
com HTTP 503, sem uma tentativa científica concluída e sem relatório de métricas.

## O que foi feito

1. **Cache de respostas desligado por padrão.** OpenAI e Colab fazem novos envios,
   mesmo quando existem respostas antigas em disco. `LLM_CACHE=leitura-escrita`
   permite habilitar o cache explicitamente; orçamento e travas continuam ativos.
2. **Erros classificados.** Timeout, conexão, rate limit, rejeição HTTP e resposta
   incompatível possuem metadados operacionais. Mensagens remotas de erro não são
   copiadas indiscriminadamente para os registros.
3. **Recuperação limitada por provedor.** OpenAI permite até três envios por prompt
   para erros transitórios. Colab mantém retentativas para 429 e evita repetir a
   mesma geração após timeout ou 503, quando o consumo pode ser desconhecido.
4. **Continuidade dos demais pares.** Depois de uma falha não fatal, o pipeline
   registra a pendência e segue para o próximo prompt/caso. Autenticação, identidade
   incompatível, orçamento e parada solicitada continuam interrompendo novos envios.
5. **Consolidação independente do sucesso da campanha.** Terminal e painel tentam
   gerar as métricas dos dados verificáveis mesmo após código de saída não zero.
   `finalizacao.json` distingue os resultados do pipeline e da consolidação.
6. **Recuperação de sessões sem resposta.** O leitor aceita JSONL vazio e permite
   recuperar execuções históricas sem JSONL quando há sessão e falha operacional
   verificáveis, preservando os arquivos originais.

O fluxo passa a ser: gerar o prompt, tentar a chamada conforme a política, registrar
a resposta ou falha operacional, continuar os pares permitidos e consolidar os dados
disponíveis ao terminar.

## Onde está a implementação

| Arquivo | Responsabilidade |
|---|---|
| [erros.py](../../../../src/pipeline/etapas/e05_geracao_llm/erros.py) | Classificação dos erros, metadados públicos e cálculo da espera entre envios. |
| [cliente_openai.py](../../../../src/pipeline/etapas/e05_geracao_llm/cliente_openai.py) | Cache optativo, retentativas, contagem de cada envio e registro de consumo incerto. |
| [cliente_colab.py](../../../../src/pipeline/etapas/e05_geracao_llm/cliente_colab.py) | Cache optativo e distinção entre falhas fatais e falhas que permitem continuar a fila. |
| [provedor.py](../../../../src/pipeline/etapas/e05_geracao_llm/provedor.py) | Configuração comum e identidade de inferência com o modo do cache. |
| [campanha.py](../../../../src/pipeline/orquestracao/campanha.py) | Continuidade entre prompts/casos, eventos operacionais e finalização da sessão. |
| [executar.py](../../../../executar.py) | Consolidação após falha e registro dos códigos de saída. |
| [controle.py](../../../../src/pipeline/painel/controle.py) | Mesmo comportamento de consolidação parcial no painel web. |
| [leitura.py](../../../../src/pipeline/etapas/e09_metricas/leitura.py) | Leitura verificável de eventos e recuperação histórica sem tentativas concluídas. |
| [calculo.py](../../../../src/pipeline/etapas/e09_metricas/calculo.py) | Resumo operacional e identificação de resultados parciais. |
| [publicacao.py](../../../../src/pipeline/etapas/e09_metricas/publicacao.py) | Publicação dos eventos em CSV e dos novos metadados. |

A configuração está exemplificada em [.env.example](../../../../.env.example).
Os cenários novos de transporte e continuidade estão em
[test_llm_resiliencia.py](../../../../tests/unit/test_llm_resiliencia.py), complementados
pelos testes de Colab, entrada curta, painel e métricas.

## Validação e evidências

| Verificação | Resultado registrado |
|---|---|
| Suíte unitária completa | 387 testes aprovados |
| Preflight dos 78 casos | Concluído com K=4 e cache de respostas desligado |
| Finalização do preflight | Pipeline e consolidação com código zero |
| Chamadas reais à LLM nesta validação | Zero |
| Recuperação do piloto antigo | Relatório parcial publicado em pasta nova; origem preservada |

O [resumo de validação](../../../../outputs/resiliencia_llm/VALIDACAO_20261102/resumo.json)
contém os hashes do código e das evidências. O log da suíte está em
[unitarios.log](../../../../outputs/resiliencia_llm/VALIDACAO_20261102/unitarios.log).

O [relatório recuperado do piloto](../../../../outputs/resiliencia_llm/RECUPERACAO_PILOTO_20261102_METRICAS/metricas.json)
informa um caso pendente, erro de servidor e zero tentativas científicas concluídas.
Recuperar essas métricas não equivale a executar novamente ou corrigir o caso.

## Cuidados metodológicos e limites

Ausência de resposta não vira R/F/M=0 nem uma tentativa científica fictícia. As taxas
por tentativa usam os registros efetivos; CR por caso mantém o conjunto solicitado.
Custos e tokens sem confirmação permanecem desconhecidos. Desligar o cache local
não desliga o cache de prefixos do provedor nem o cache de validação funcional/SAST.

A execução pode terminar com pendências e relatório parcial quando a API não se
recupera. O código de saída continua indicando falha, mesmo quando a consolidação
funciona. Orçamento limita novos envios; consumo remoto desconhecido não permite
garantir um teto financeiro exato. Encerramento forçado ou falha de disco ainda
podem impedir a finalização.

O [README da feature](README.md) apresenta a tabela completa de erros, a política
por provedor e os comandos para validar e reproduzir a recuperação offline.
