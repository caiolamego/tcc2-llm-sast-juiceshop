# Cobertura funcional revisada — relacionada_v2

A política optativa `relacionada_v2` executa os grupos de comportamento revisados
para **todos os arquivos alterados pelo patch**. Não usa uma suíte ampla como
fallback. Arquivos desconhecidos, avaliação comprometida ou lacunas impedem F
positivo; uma falha funcional comprovada ainda pode produzir F=0. R/M continuam
medidos pelo SAST global depois da remoção dos testes temporários.

A [revisão por ocorrência](../config/cobertura_funcional_v1.yaml) é a fonte das
associações. O [mapa 2.0](../config/mapa_testes_relacionados_v2.yaml) contém sua
união por arquivo e seu hash. Um caso adequado pode ficar bloqueado por outro
comportamento insuficiente no mesmo arquivo: alterar uma biblioteca compartilhada
não autoriza ignorar suas outras obrigações revisadas.

O baseline 2.0 registra compilações, grupos, identidades de testes, resultados,
JUnit, ambiente e hashes. Os testes descobertos são os casos enumerados no JUnit;
os ignorados permanecem identificados, sem serem contados como executados. Os
testes obrigatórios precisam passar no baseline e continuar sendo executados após
o patch. Testes já reprovados não são a única prova do comportamento. Aplicam-se
as três definições F/D existentes, com o conjunto D explicitamente versionado.

## Uso optativo

Na raiz, com a `.venv` e o alvo preparados:

```bash
.venv/bin/python executar.py --config config/execucao_cobertura.exemplo.yaml --mostrar-comando
.venv/bin/python executar.py --config config/execucao_cobertura.exemplo.yaml
```

O exemplo é **preflight**, K=1, quatro casos e P1/P2: valida revisão, baseline,
ambiente, SAST e prompts, sem criar cliente LLM nem executar testes funcionais.
A configuração padrão `config/execucao.yaml` permanece inalterada.

O painel também aceita esse arquivo:

```bash
.venv/bin/python painel.py --config config/execucao_cobertura.exemplo.yaml
```

Se já houver um painel aberto, encerre-o quando estiver ocioso antes de iniciar
outro. Nas tentativas, o painel apresenta domínios, grupos e motivos; os detalhes
incluem baseline, compilações e contagens esperadas/executadas/ignoradas. A ausência
desses campos em uma execução antiga não representa cobertura Angular.

Na interface completa, acrescentar `--politica-validacao relacionada_v2`,
`--cobertura-funcional config/cobertura_funcional_v1.yaml`, o mapa 2.0 e o baseline
2.0. Novas execuções usam contrato 4.0; políticas anteriores mantêm seus contratos.
Retomadas recusam mudanças na revisão, mapa, D, avaliadores, adaptadores, baseline
ou ambiente. O cache funcional identifica também as dependências frontend e não
reutiliza cobertura insuficiente. O cache SAST permanece separado.

## Auditar e validar são operações separadas

O auditor só lê entradas e publica relatórios determinísticos em destino novo:

```bash
.venv/bin/python scripts/audit/audit_functional_coverage.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 \
  --mapa-testes config/mapa_testes_relacionados_v2.yaml \
  --revisao config/cobertura_funcional_v1.yaml \
  --baseline-testes outputs/feature06/BASELINE_06/baseline_testes.json \
  --saida outputs/cobertura_funcional/NOVA_AUDITORIA
```

Sem `--baseline-testes`, ele informa a revisão sem atribuir prontidão. Não instala
dependências, inicia serviços ou executa testes/Semgrep/LLM. Códigos 0/2/1 indicam
sucesso, argumentos inválidos e falhas de dados/execução. Locks remanescentes
exigem investigar o processo proprietário; destinos existentes são recusados.

O comando separado `scripts/experiment/validate_functional_coverage.py` recebe os
mesmos cinco argumentos obrigatórios; `--grupos` restringe os IDs separados por
vírgula e `--controles` executa as três regressões deliberadas. Ele reserva a
execução, exige checkout limpo no commit fixado e preserva resultados parciais.
Use sempre uma saída nova. Não execute simultaneamente ao pipeline.

## Domínios e limites

- Servidor: TypeScript da raiz e arquivos unitários selecionados.
- API: arquivos explícitos com a preparação do Juice Shop, HTTP local e lock de API.
- Frontend: build Angular development com AOT em diretório temporário e arquivos
  explícitos de teste, Vitest/jsdom, sem watch. Timeout de 300 segundos por build
  e grupo; repetições incluem o grupo inteiro.

JUnit normaliza `arquivo :: suíte > teste`. Os testes adicionais são versionados
em `tests/functional/juice_shop/`, materializados com criação exclusiva e removidos
em `finally`; alterações desconhecidas interrompem a avaliação. Nenhum arquivo de
avaliação novo permanece no universo do scan SAST.

jsdom e mocks medem os contratos declarados, não navegação real, layout, execução
de exploração ou integração completa com backend. A revisão Angular não encontrou
evidência suficiente para acrescentar testes ao conjunto D: chamadas a mocks com
payload malicioso continuam F conforme o critério vigente. Isso pode limitar a
aceitação de correções e está documentado, sem reclassificação retrospectiva.

Consulte as [contagens, evidências e pendências da entrega](../features/06-cobertura-funcional/ENTREGA.md).
