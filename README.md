# Correção de vulnerabilidades em código com LLMs

Pipeline que lê os alertas de análise estática (Semgrep) sobre o OWASP Juice Shop, pede a uma LLM uma
correção para cada alerta, aplica a correção numa cópia isolada do projeto e valida o resultado.

Trabalho de Conclusão de Curso 2, Engenharia de Software, Faculdade de Ciências e Tecnologias em
Engenharia (FCTE), Universidade de Brasília.
**Autores:** Matheus de Siqueira Brant e Caio Magalhães Lamego.
**Orientadora:** Profa. Dra. Elaine Venson.

## Quando uma correção é válida

Uma tentativa só conta como correção válida quando os três critérios valem ao mesmo tempo:

| Variável | Critério |
|:---:|---|
| `R` | O alerta original deixou de ser detectado na reanálise estática |
| `F` | Os testes funcionais continuam passando |
| `M` | Nenhum alerta de segurança novo apareceu |

Métrica principal: **TRV = Σ(R·F·M) / m**, em que `m` é o número de tentativas. As estratégias de prompt
são P1 (simples), P2 (raciocínio guiado), P3 (RAG simplificado) e P4 (RAG + raciocínio guiado), tentadas
nessa ordem até a primeira correção válida.

## Como rodar

Tudo roda no Docker, com a mesma imagem para todos. O guia completo está em
[docs/docker.md](docs/docker.md).

```bash
make docker-import ARQUIVO=/caminho/tcc2-ambiente.tar
```
```bash
make docker-check
```
```bash
make docker-setup K=4
```
```bash
make docker-preflight
```
```bash
make docker-painel
```

O painel abre em http://127.0.0.1:8765. `make docker-help` lista todos os atalhos. A execução real
(`make docker-real` ou pelo painel) chama a LLM e usa a chave e os limites do `.env` (modelo em
`.env.example`).

## Onde está cada coisa

```text
README.md              este arquivo
executar.py            atalho de linha de comando: preflight, dry-run ou execução real
painel.py              painel web local
Makefile               atalhos de testes e do Docker
Dockerfile, compose.yaml, docker/
                       ambiente único (docs/docker.md)
src/pipeline/          código do pipeline           → mapa das etapas: src/pipeline/README.md
scripts/               comandos avulsos             → scripts/README.md
config/                entradas congeladas e configurações de execução → config/README.md
knowledge_base/        base do RAG simplificado (10 documentos)
rules/                 regras Semgrep escritas pelo grupo (rodadas 1–12)
tests/                 testes do projeto (unit), das regras (integration)
                       e testes próprios injetados no Juice Shop (functional)
notebooks/             servidor do modelo Qwen no Colab
docs/                  método, guias, planejamento, auditorias e histórico → docs/README.md
outputs/               todos os resultados          → outputs/README.md
workspace/, .cache/    só locais: worktrees do Juice Shop, caches e travas
```

## Arquitetura

O código segue o estilo **dutos e filtros**: cada etapa do §3.8 do TCC é um filtro que lê e grava
artefatos, e o orquestrador `src/pipeline/orquestracao/campanha.py` só encadeia as etapas. O mapa etapa → código →
artefato está em [src/pipeline/README.md](src/pipeline/README.md).

Parte do código entra na identidade científica do experimento (baseline oficial, referência Docker e
contrato de cada execução). Mover ou renomear esses arquivos exige gerar de novo o baseline e a referência
(`make docker-baseline`), como foi feito na reorganização de 26/10/2026. A lista e o motivo estão no mesmo documento e
em [config/README.md](config/README.md).

## Resultados

A campanha oficial (52 casos, P1–P4, gpt-4.1-mini) está em
`outputs/campanha_docker/AMP_PAINEL_20261019T183425Z_282e13b4/`, com as métricas na pasta irmã
`_METRICAS`. O papel de cada pasta de resultados está em [outputs/README.md](outputs/README.md).

## Mais detalhes

- O README anterior, com estratégias, métricas, validação em camadas e os comandos de cada feature:
  [docs/guias/referencia_detalhada.md](docs/guias/referencia_detalhada.md).
- O que mudou de lugar na reorganização de 26/10/2026: [docs/historico/README.md](docs/historico/README.md).

## Aviso

O OWASP Juice Shop é uma aplicação **deliberadamente vulnerável**, usada aqui como objeto de estudo. Nunca
a exponha em rede pública ou em ambiente compartilhado. Todo o experimento roda localmente, em cópias
isoladas.

Este repositório não contém, nem deve conter, chaves de API. Se uma chave for exposta, revogue-a no painel
do provedor.

## Licença

MIT. Veja [LICENSE](LICENSE).
