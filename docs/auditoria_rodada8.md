# Rodada 8 — quatro candidatos prioritários

Esta rodada encerra o pedido atual: investigar e incluir quatro candidatos.
Não inicia a rodada 9 nem executa a LLM. A meta anterior de sete entre dez
candidatos não foi atingida por esta rodada (quatro entre dez).

## Resultado

| Indicador do perfil exploratório acumulado | Antes | Depois |
|---|---:|---:|
| Alertas brutos | 64 | 68 |
| Alertas confirmados por revisão | 43 | 47 |
| Falsos positivos | 19 | 19 |
| Inconclusivos | 2 | 2 |
| Desafios distintos confirmados | 37 | 41 |

Perfis somados: `default`, `custom-rules` e rodadas 2–8. A matriz preserva
também scans históricos sobrepostos: suas 99 observações **não** representam
99 vulnerabilidades distintas. Ela mantém 113 chaves de desafios únicas.

| Candidato incluído | Evidência e teste |
|---|---|
| `dataExportChallenge` | Emails distintos cadastráveis colidem após mascaramento; a rota real de exportação seleciona pedido alheio pela identidade mascarada. Controle com identidade única não retorna o pedido. |
| `negativeOrderChallenge` | Quantidade -2 atravessa a validação da rota e persiste no SQLite; o checkout real calcula total -20 e solicita débito negativo. Controle exige inteiro positivo. |
| `registerAdminChallenge` | POST anônimo pela API gerada real persiste `role: admin`; controle impõe `customer` no servidor. |
| `forgedFeedbackChallenge` | POST com CAPTCHA válido persiste `UserId` de outra pessoa; controle impõe a identidade autenticada. CAPTCHA inválido é rejeitado. |

Três regras produziram quatro alertas: exportação, histórico de pedidos,
validação de quantidade e criação de recursos CRUD. O alerta do CRUD tem
duas associações confirmadas, cadastro e feedback. O alerta no histórico
de pedidos registra o mesmo problema de seleção por email mascarado, mas
**não** acrescenta um desafio. Assim, quatro alertas novos e quatro desafios
novos são contagens diferentes, coincidentes nesta rodada.

## Critérios e limites

- As regras não utilizam nomes de desafios, caminhos exclusivos ou linhas
  do alvo. Exemplos positivos, negativos e controles externos conhecidos
  estão em `rules/rodada8`.
- A regra de CRUD é um sinal de auditoria de baixa confiança: expor ações
  padrão não prova vulnerabilidade. A confirmação depende da revisão dos
  middlewares e de requisições HTTP com Express, Finale, Sequelize e SQLite
  reais. `excludeAttributes` do Finale não é uma lista de campos autorizados
  para criação. Recursos com `actions` explícito ficam fora desta regra,
  inclusive quando inseguros: existe essa limitação de cobertura.
- A regra de quantidade não comprova ausência de validação em outro
  middleware. Um exemplo protegido externamente documenta esse falso
  positivo conhecido. O fluxo do alvo foi testado antes da confirmação.
- Os testes usam rotas, modelos e trechos de configuração do commit alvo;
  **não são um teste E2E do servidor completo**. Identidade autenticada e
  dependências auxiliares são simuladas. CAPTCHA e persistência dos campos
  analisados usam os componentes reais; associações completas dos modelos
  não são reconstruídas.
- Na exportação, o armazenamento de pedidos é simulado. No checkout,
  estoque, carteira, pedidos e PDF são simulados: observa-se a solicitação
  de débito negativo, não uma movimentação financeira real. Controles
  protegidos existem somente no teste e não alteram o Juice Shop.
- Dependências diretas verificadas: Express 4.22.1, Finale 1.2.2,
  Sequelize 6.37.3, sqlite3 5.1.7 e clarinet 0.12.6; Node 24.14.0.
  O alvo não possui lockfile. São versões compatíveis com suas declarações,
  não comprovação de equivalência a qualquer instalação do Juice Shop.
  O lockfile do ambiente de teste foi arquivado para reprodução.

## Artefatos

- [Matriz CSV](../outputs/auditoria_sast/rodada8/matriz_desafios.csv) e
  [JSON](../outputs/auditoria_sast/rodada8/matriz_desafios.json).
- [Comparação](../outputs/auditoria_sast/rodada8/resumo.json),
  [scan](../outputs/auditoria_sast/rodada8.json) e
  [manifesto com hashes](../outputs/auditoria_sast/manifesto-rodada8.json).
- [Scan repetido](../outputs/auditoria_sast/rodada8/repeticao/rodada8.json)
  e seu manifesto no mesmo diretório.
- [Triagem dos quatro alertas](../config/auditoria_desafios_rodada8.yaml).
- [Testes arquivados](../outputs/auditoria_sast/rodada8/testes/testes.tap),
  manifesto de testes e dependências no mesmo diretório.

O baseline JS001–JS012, os snapshots anteriores, a revisão SSTI e a seleção
antiga de candidatos à correção foram preservados. A seleção antiga ainda
não representa a cobertura desta rodada. Não foi recalculado um número
definitivo de causas independentes: desafios e alertas não equivalem a
correções independentes.

## Reprodução

Verificação executada: 20/20 conjuntos de exemplos Semgrep aprovados;
cinco cenários de fluxo aprovados (seis testes TAP contando o agrupador);
36 testes Python aprovados, incluindo equivalência dos dois scans e
imutabilidade dos alertas anteriores. Ambos os scans retornaram os mesmos
quatro achados, sem erros ou timeouts reportados.

Usar o alvo limpo no commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`,
Semgrep 1.177.0 e executar a partir da raiz deste repositório.
O scan usa as exclusões existentes e timeout de 30 segundos por regra/arquivo.
Escolher um diretório novo para não sobrescrever os arquivos arquivados:

```bash
python3 scripts/scan_semgrep_exploratorio.py --worktree /caminho/juice-shop --perfis rodada8 --timeout 30 --saida /caminho/novo-scan
semgrep --test --config rules rules
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/report_rodada8.py
```

Para reproduzir o ambiente de integração a partir do lockfile arquivado,
instalar as dependências em seu próprio diretório, nunca no código-alvo:

```bash
npm ci --prefix outputs/auditoria_sast/rodada8/testes/dependencias --no-audit --no-fund
JUICE_SHOP_WORKTREE=/caminho/juice-shop ROUND8_DEPS="$PWD/outputs/auditoria_sast/rodada8/testes/dependencias" node --test scripts/test_rodada8_flows.mjs
```

Para arquivar uma nova execução com hashes, usar `scripts/verify_rodada8.py`
com `--worktree`, `--deps` (diretório que contém o package.json instalado)
e `--saida` apontando para um diretório ainda inexistente.

O próximo trabalho, se solicitado, é consolidar a seleção versionada de
causas para correção, revisando duplicatas e mantendo os falsos positivos
fora das tentativas da LLM. Esta implementação termina na rodada 8.
