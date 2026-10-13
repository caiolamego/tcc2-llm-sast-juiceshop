# Estrutura do projeto

## Código e comandos

`src/pipeline/` contém os componentes de SAST, LLM, prompts, patches, worktrees, validação e o orquestrador. Esta reorganização não altera a lógica experimental nem extrai novos módulos.

Os comandos são separados em `scripts/setup/`, `scripts/audit/`, `scripts/experiment/` e `scripts/reports/`. As entradas antigas da raiz de `scripts/` foram removidas para evitar duplicidade na navegação. Use os caminhos das subpastas. O script `scripts/setup/setup_target.sh` localiza a raiz do repositório antes de preparar o alvo.

`scripts/_bootstrap.py` configura imports da raiz e de `src/`; os comandos usam `pipeline.caminhos.RAIZ_REPO` para acessar dados independentemente da localização do script. Execute os exemplos do README a partir da raiz. A resolução interna dos arquivos não depende do diretório corrente; argumentos relativos fornecidos pelo usuário continuam relativos ao diretório corrente.

## Testes

Os testes Python estão em `tests/unit/`. Execute `make test-unit` ou `python3 -m unittest discover -s tests/unit -p 'test_*.py'`. As regras e suas fixtures `.ts` permanecem em `rules/rodada1/` até `rules/rodada12/`; execute `make test-rules`. É possível selecionar executáveis com `make test-unit PYTHON=/caminho/python` e `make test-rules SEMGREP=/caminho/semgrep`.

Os testes de integração `.mjs` estão em `tests/integration/rodadaN/test.mjs`. Todas as rodadas têm README e manifesto com o mesmo formato; nas rodadas 1–6 a integração está explicitamente não implementada. Fontes originais em `tests/integration/historico/` permitem conferir hashes antigos. Use `scripts/audit/test_rodada.py` como entrada comum. A execução exige Node, alvo e dependências específicas e não faz parte de `test-unit`.

A verificação dos cenários do runner está em `scripts/experiment/validate_runner_scenarios.py`. Ela altera temporariamente worktrees e grava evidências; só deve ser executada como verificação experimental explícita. Use o novo caminho; a entrada antiga foi removida.

## Dados e documentação

`outputs/sast_antes/` preserva o catálogo histórico JS001–JS012. A expansão da auditoria fica em `outputs/auditoria_sast/`; seus alertas não são automaticamente o catálogo usado pelo orquestrador. Esta mudança de pastas não seleciona casos, exclui falsos positivos nem redefine métricas.

Todos os arquivos de `outputs/` são preservados nesta reorganização, incluindo referências a comandos antigos. As regras mantêm seu conteúdo; os `.mjs` originais estão preservados em `tests/integration/historico/`, enquanto as versões executáveis ajustam o caminho relativo do catálogo. Relatórios da auditoria estão em `docs/auditoria/`; protocolo, caderno e critérios F/D continuam em `docs/`.

## Pendências separadas

O `.gitignore` permanece inalterado. A preservação dos artefatos oficiais ignorados (prompts, testes, reanálises e códigos corrigidos) precisa de uma decisão própria de armazenamento e recuperação. Também permanecem pendentes RAG/P3/P4, integração do catálogo ampliado, CSVs, RRIS e confirmação dinâmica final.
