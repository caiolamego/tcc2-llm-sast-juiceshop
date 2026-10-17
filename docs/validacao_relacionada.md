# Validação somente da funcionalidade afetada

Decisão de 16/10/2026: a configuração de entrada `config/execucao.yaml` seleciona
`politica_validacao: relacionada_v1` e o mapa explícito de testes. Mantém os dois
casos, P1–P4, cache desligado e os limites do `.env`. Em 17/10/2026, K foi
ajustado para 2 para usar as duas worktrees nas próximas execuções. A alteração
do YAML não modifica o número de workers de uma execução já iniciada. Nenhuma execução real
é iniciada ao alterar a configuração.

## Fluxo

1. Aplicar o patch e identificar todos os arquivos efetivamente alterados.
2. Compilar/verificar tipos com T0 (`tsc --noEmit`).
3. Executar a união dos testes unitários e de API explicitamente mapeados para
   esses arquivos. A repetição de uma falha repete o comando relacionado; não
   chama a suíte inteira.
4. Executar SAST global e comparar R/M por ocorrência, inclusive quando T0 ou os
   testes relacionados reprovam. O perfil e o comparador não mudam.
5. Registrar escopo, seleção, cobertura e resultados; restaurar a worktree.

T3 e T4 amplos são registrados como `nao_aplicavel`. A política
`otimizada_v1` da feature 05 continua disponível com confirmação ampla, assim
como `historica_v1`. O CLI mantém a política histórica como padrão de
compatibilidade; o lançador e o painel usam a seleção explícita do YAML.

## Seleção atual

| Arquivo alterado | Unitários | API |
|---|---|---|
| `routes/login.ts` | Ausência declarada | `test/api/login.test.ts` |
| `routes/keyServer.ts` | `test/server/keyServer.unit.test.ts` | `test/api/file-serving.test.ts` |

O mapa seleciona arquivos de teste completos. Isso inclui os hooks, os testes de
funcionamento normal e os testes de desafios presentes nesses arquivos; não
seleciona um único `it` nem elimina D. Alterações em múltiplos arquivos exigem a
união dos seus testes, sem duplicatas.

## Lacunas não disparam a suíte inteira

Antes de criar o cliente LLM, o modo ampliado recusa casos selecionados que não
possuam associação específica revisada no mapa. Os outros 44 arquivos hoje com
`modo: amplo` precisam de mapeamento antes de entrar nesta política.

Se o patch modificar um arquivo adicional desconhecido/compartilhado, a validação
executa T0, os testes disponíveis e o SAST. A seleção é marcada como insuficiente;
nenhuma suíte ampla é acionada automaticamente. Valores de F que seriam positivos
ficam `null`, com `indeterminada_funcional`, e não podem causar aceite/parada da
cadeia. Uma falha funcional já comprovada continua F=0. Seleção vazia ou API
mapeada mas desabilitada também não produz F positivo. Evidência com cobertura
insuficiente não é reutilizada pelo cache funcional.

## Interpretação científica

Nesta política, F se refere à compilação e ao comportamento coberto pelos testes
mapeados, sem comprovar ausência de regressões em toda a aplicação. As três
separações F/D e a regra de parada continuam iguais; muda o escopo observado.
R/M continuam provenientes do SAST global. Os registros usam cobertura
`servidor_relacionado` ou `insuficiente`, separadamente da política contratada.

O contrato 3.0 inclui a política, mapa, implementação e ambiente; retomar uma saída
antiga com esta política é recusado. Use uma execução/saída nova. Os resultados
históricos e a matriz da feature 05 permanecem preservados e mediram políticas
com cobertura diferente. Seus tempos não representam a política relacionada e
não devem ser apresentados como uma medição dela.

## Comandos

Prévia sem chamar LLM, Semgrep ou testes do alvo:

```bash
python executar.py --mostrar-comando
```

Executar somente o preflight (SAST real e montagem dos prompts, sem LLM/patches):

```bash
python executar.py --modo preflight
```

A execução real continua sendo `python executar.py` e respeita o orçamento do
`.env`. Esta alteração foi verificada com testes sintéticos e leitura do mapa;
nenhuma nova chamada à LLM, scan, replay ou teste funcional do Juice Shop foi
executado para ativá-la. O tempo real desta política ainda precisa ser medido.
