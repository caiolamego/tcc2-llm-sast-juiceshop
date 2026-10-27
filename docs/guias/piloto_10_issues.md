# Piloto manual com dez issues

A entrada padrão está configurada para execução real de dez casos preparados
pela auditoria da feature 06, em dez arquivos de servidor/API. Não é uma amostra
aleatória nem uma campanha dos 78 casos. A escolha permite observar fluxos
diferentes sem exigir dependências Angular nas worktrees adicionais.

| Caso | Arquivo | Alerta avaliado |
|---|---|---|
| `AMPfb154534099cb3ca` | `routes/login.ts` | SQL na autenticação |
| `AMP95adf572d3c6677f` | `routes/keyServer.ts` | Caminho na entrega de arquivos |
| `AMP966898b58995c2e3` | `routes/basket.ts` | Consulta de cesta por identificador |
| `AMP2ab02d839a97d47d` | `routes/search.ts` | SQL na busca de produtos |
| `AMP2bf027ab02da7396` | `routes/currentUser.ts` | Resposta JSONP |
| `AMP5c9cd865e297e422` | `routes/likeProductReviews.ts` | Atualização atrasada do contador |
| `AMP8acdcde5bd3bac8f` | `routes/deluxe.ts` | Atualização de perfil por modo opcional |
| `AMP20721d202c8b96d6` | `routes/trackOrder.ts` | Consulta dinâmica de pedido |
| `AMP9ea0dd6316734fd8` | `routes/changePassword.ts` | Senha atual opcional |
| `AMPf7a5e2edd454d398` | `lib/xml.ts` | Expansão de entidades XML |

Os nomes descrevem os alertas; aprovação funcional ou remoção de alerta não
confirmam, por si só, a segurança da correção.

## Iniciar manualmente

Na raiz do repositório:

```bash
python3 executar.py
```

O lançador usa a `.venv`, cria uma saída nova em `outputs/execucoes/` e consolida
as métricas ao terminar. A configuração fica em `config/execucao.yaml`:

- P1/P2/P3/P4, com a parada vigente após aceite estrito de cada issue: **até 40
  tentativas**, podendo haver menos quando a cadeia termina antes.
- K=4: até quatro issues podem avançar em worktrees distintas. As estratégias de uma
  mesma issue continuam em sequência; testes de API continuam serializados.
- Política `relacionada_v2`, mapa 2.0 e baseline corrigido da revalidação. Lacunas não
  autorizam F positivo e não disparam suíte ampla como fallback.
- Cache de validação desligado para observar as medições desta execução.
  O cache LLM existente permanece ativo; respostas já disponíveis podem ser
  reutilizadas e aparecem com `do_cache: true`, sem nova cobrança.

O `.env` local mantém a chave e o teto `MAX_USD=1`. O limite acumulado foi
ajustado de 8 para 48 chamadas, considerando as oito já registradas e até 40
novas. O histórico de consumo não foi apagado. Esses são limites globais entre
execuções; outras chamadas futuras também consomem o saldo.

Para conferir os comandos ou repetir somente o preflight:

```bash
python3 executar.py --mostrar-comando
python3 executar.py --modo preflight
```

Preflight verifica cobertura, ambientes, reprodução SAST e prompts, sem chamar
a LLM ou executar testes funcionais. A preparação do piloto não inicia a execução
real automaticamente.

## Acompanhar e consultar respostas

```bash
python3 painel.py
```

Abra http://127.0.0.1:8765 e confira **dez casos, K=4 e relacionada_v2** antes de
iniciar. Use o painel ou o terminal por vez. Uma página já aberta recebe a nova
configuração no próximo carregamento quando não houver execução ativa.

O terminal/painel informa a pasta da execução. Dentro dela:

| Caminho | Conteúdo |
|---|---|
| `prompts/` | Mensagens enviadas em cada estratégia |
| `respostas_llm/` | Resposta da LLM no campo `texto`, uso e indicação de cache |
| `patches/` | Alterações geradas |
| `testes/` | Resultados funcionais |
| `sast_depois/` | Reanálise e comparação R/M |
| `resultados_consolidados/execucoes.jsonl` | Uma linha por tentativa, classificação e tempos |

As métricas ficam na pasta irmã com sufixo `_METRICAS`. As respostas e os patches
anteriores continuam nas saídas originais. Para interromper pelo painel, use
**Encerrar após tentativa atual**; os resultados parciais são preservados.

## Preparação do ambiente

O primeiro preflight identificou conteúdo instalado diferente em `wt-2` apesar
dos lockfiles iguais. A preparação alinhou com `wt-1` o executável local esbuild,
os builds nativos opcionais de iltorb/libxmljs2 e os bytecodes de instalação do
node-gyp. O executável anterior foi preservado em `.cache/piloto10_preparacao/`.
Não se alterou o baseline para aceitar ambientes divergentes, nem se instalaram
dependências frontend em `wt-2`.

O preflight e os testes da preparação estão registrados separadamente dos
resultados reais. Essa preparação não é evidência de que as dez issues foram
corrigidas.


Foram preparadas `wt-3` e `wt-4` no mesmo commit, com cópias isoladas das
dependências de `wt-1` e do lockfile local. O novo preflight confere as quatro
worktrees contra o baseline funcional. Não há compartilhamento de uma mesma
pasta `node_modules` entre workers. Testes de API permanecem serializados; K=4
não implica quatro suítes de API simultâneas nem ganho de quatro vezes no tempo.

O painel foi reiniciado para carregar a política da feature 06 e a nova
configuração. Abrir a página não inicia chamadas à LLM: selecione **Real** e
clique em **Iniciar pipeline** quando quiser executar.


A execução real inicial revelou falta de builds nas worktrees novas. A política
atual inclui esses artefatos no gate e aguarda a inicialização antes dos testes.
Falhas operacionais não são mais convertidas em testes funcionais reprovados.
O baseline corrente é `outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE/`.
A [revalidação sem LLM](../auditoria/correcao_validacao_piloto10.md) preserva a
execução inicial e permite comparar as mesmas correções em ambiente preparado.

## Worktrees adicionais preparadas

A configuração atual usa K=4. `wt-5` e `wt-6` foram preservadas no disco e não são utilizadas pela configuração padrão. Elas foram preparadas no mesmo commit, com cópias independentes das dependências, lockfile e artefatos de preparação API. O preflight deve continuar exigindo compatibilidade de ambiente e baseline para todas as seis. A criação das worktrees não executa a campanha.

A máquina possui 16 CPUs lógicas e cerca de 15 GiB de RAM total; K=6 precisa ser avaliado em execução, pois compilação/SAST concorrem por memória. Não há ganho garantido sobre K=4. Os testes de API continuam serializados e `COLAB_MAX_IN_FLIGHT=1` mantém uma geração por vez no Colab. Se houver swap significativo ou piora de desempenho, reduza `k` para 4 no YAML.
