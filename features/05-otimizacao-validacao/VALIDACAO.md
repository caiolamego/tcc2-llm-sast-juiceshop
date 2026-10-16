# Testar a execução após implementar a feature 05

**Status:** replay executado; resultados e limitações em [ENTREGA.md](ENTREGA.md).  
**Objetivo:** escolher uma configuração mais eficiente antes da campanha dos 78 casos.

## 1. Preparar e registrar a referência

- [ ] Capturar hashes dos artefatos históricos, mapas, fontes e perfil.
- [ ] Registrar versões efetivas de Python, Node, npm, TypeScript e Semgrep, commit
  alvo, lockfile e instalação das dependências.
- [ ] Conferir espaço e memória para duas worktrees; preparar somente as necessárias,
  usando o lockfile, sem modificar `workspace/catalogo-alvo/`.
- [ ] Conferir que nenhuma execução do terminal ou painel usa essas worktrees.
- [ ] Executar `make test-unit PYTHON=.venv/bin/python` e os demais checks aplicáveis.

A referência comportamental é o runner histórico preservado, medido novamente no
mesmo ambiente. Os tempos antigos servem como contexto, não como comparação direta
com uma máquina/configuração diferente. A feature deve tornar possível selecionar
a política histórica sem exigir o código antigo em uma saída de execução antiga.

## 2. Implementar uma entrada de replay sem cliente LLM

Criar `scripts/experiment/benchmark_validation.py` para ler os patches do piloto,
verificar seus hashes e aplicá-los isoladamente sobre o commit fixado. O replay
deve executar validação e SAST reais, mas jamais instanciar cliente LLM ou gerar
novas correções. Não depender apenas da ausência de chave para garantir isso.

Usar os oito `.diff` de
`outputs/piloto_2_issues/AMP_PILOTO_2_REAL_20261014/patches/`, associados às duas
ocorrências e às quatro estratégias. Cada patch parte do alvo original; não aplicar
patches cumulativamente. Restaurar a worktree em `finally`, inclusive em falha ou
pedido de parada.

Publicar em diretório novo sob `outputs/feature05/`, recusando sobrescrita e
sobreposição com entradas. Essa saída é um benchmark de replay, não uma nova
execução real de correções. Não adicionar suas observações aos JSONLs históricos.

Interface prevista para implementação:

```bash
# Comandos implementados; cada saída deve ser nova.
.venv/bin/python scripts/experiment/benchmark_validation.py \
  --origem outputs/piloto_2_issues/AMP_PILOTO_2_REAL_20261014 \
  --politica-validacao historica_v1 --cache-validacao desligado \
  --k 1 --saida outputs/feature05/REPLAY_REFERENCIA_K1

.venv/bin/python scripts/experiment/benchmark_validation.py \
  --origem outputs/piloto_2_issues/AMP_PILOTO_2_REAL_20261014 \
  --politica-validacao otimizada_v1 \
  --mapa-testes config/mapa_testes_relacionados.yaml \
  --cache-validacao leitura-escrita \
  --repeticao-api ampla --k 1 \
  --saida outputs/feature05/REPLAY_OTIMIZADO_K1
```

O benchmark usa catálogo, perfil e baseline da origem conferidos por hash, ou exige
alternativas explicitamente compatíveis. Não substituir regras divergentes nem
retomar a execução antiga com um contrato novo para viabilizar o teste.

## 3. Executar em etapas

1. **Smoke test:** um patch de cada issue, K=1, cache desligado. Verificar aplicação,
   testes realmente executados, SAST, registro e restauração.
2. **Referência:** replay dos oito patches, política histórica, K=1, sem cache.
3. **Otimizado frio:** os mesmos oito patches, K=1 e namespace novo de cache. A
   primeira ocorrência de uma identidade mede tudo; duplicatas posteriores podem
   reutilizar. Registrar quais patches produziram estados efetivamente iguais.
4. **Otimizado quente:** repetir em outra saída com o mesmo cache compatível.
   Separar os ganhos de reutilização dos ganhos de seleção de testes.
5. **Repetição de API:** comparar ampla/seletiva com cache desligado, incluindo
   login. Se o replay não reproduzir as falhas do piloto, registrar essa limitação
   e não declarar equivalência real de uma repetição que não aconteceu.
6. **K=2:** repetir com duas worktrees prontas, controlando cache e política de
   repetição para não confundir paralelismo com reuso de evidência.

Não executar uma matriz completa desnecessária antes do smoke test. Para reduzir
efeitos de aquecimento, alternar a ordem referência/otimizado nas repetições. Após
o primeiro ciclo correto, fazer pelo menos três repetições comparáveis dos cenários
usados para afirmar ganho, reportando mediana e intervalo observado.

Se nenhum patch real for idêntico, não fabricar hits no relatório do piloto. Usar
fixtures sintéticas para testar o cache e registrar que sua economia na campanha
ainda é desconhecida.

## 4. Relatório comparativo

Publicar JSON/CSV e resumo Markdown com:

- Identidade/hash do patch e do estado final; caso, estratégia e política.
- R, M e as três definições de F; falhas persistentes/intermitentes e cobertura.
- Testes selecionados, executados, repetidos e dispensados, com justificativas.
- Tempos por etapa, lookup, esperas de lock, restauração e parede da sessão.
- Cache frio/quente e hits/misses por componente; medições efetivamente executadas.
- Uso de recursos, falhas técnicas, cancelamento, integridade e limpeza final.
- Aceleração `tempo_referencia / tempo_otimizado` e economia percentual, somente
  entre cenários comparáveis, declarando se preparação/dependências foram incluídas.

Qualquer divergência de classificação deve ser investigada, inclusive uma mudança
de “indeterminado” para resultado conclusivo. Não atribuir divergência a ganho de
qualidade do patch: os patches são os mesmos. Não misturar replays e cache hits
como novas amostras independentes nas métricas do TCC.

## 5. Escolher a configuração e testar pelo painel

- [ ] Revisar o relatório e escolher política, cache, repetição e K pelas evidências.
- [ ] Registrar a decisão e os hashes no protocolo e no `ENTREGA.md` da feature.
- [ ] Fazer um preflight novo para as duas issues e conferir o contrato escolhido.
- [ ] Verificar iniciar/parar no painel com processo sintético e conferir os novos
  indicadores de tempos e reuso antes de usar uma execução real.
- [ ] Criar uma saída nova para eventual piloto com LLM e manter os artefatos anteriores.

**A etapa inicial após implementar será o replay sem API.** Uma rodada posterior
com LLM deve ser solicitada separadamente, com limites do `.env` e sem resetar o
orçamento acumulado. Somente depois da avaliação do piloto recomendar a campanha
dos 78 casos; até 312 tentativas são possíveis, não garantidas, pela regra de parada.
