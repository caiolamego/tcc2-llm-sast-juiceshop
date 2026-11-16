# Correção da aplicação por indentação

Entrega de 19/10/2026, sem commit, push ou chamadas à LLM.

As oito tentativas não aplicadas de `administration.component.ts` usavam
recuo de dois espaços dentro dos loops, enquanto o arquivo original tinha
mais oito espaços de contexto. A busca literal falhava.

A política nova mantém a correspondência exata prioritária. Para blocos JS/TS
com duas ou mais linhas, o fallback aceita somente correspondência única por
recuo uniforme, com conteúdo das linhas idêntico. Não corrige nomes, aspas,
operadores, espaços internos ou trechos inventados. Blocos ambíguos e linguagens
sem suporte continuam recusados. Sem TypeScript local confiável, não há fallback.

O AST TypeScript confere que o ajuste não altera tokens do código original nem
da solução proposta, protegendo em particular strings, regex, JSX e templates.
Os testes reais no Docker recusaram mudanças de conteúdo em template multilinha
no original e na substituição, sem escrever nos arquivos temporários.

## Evidência

- Replay de oito respostas arquivadas: **8/8 aplicadas** em cópias temporárias.
- As respostas e o registro original mantiveram os hashes conferidos no replay.
- Nenhuma edição aplicada nas worktrees reais; nenhum SAST ou teste funcional executado no replay.
- 358 testes unitários passando localmente e dentro do Docker.
- Referência do Docker permanece íntegra; não foi necessário reconstruir a imagem nem regenerar baseline.

Relatório: [`replay.json`](../outputs/revalidacoes/ANCORAS_INDENTACAO_V1/replay.json).
As substituições e os diffs estão nas pastas `codigos/` e `patches/` dessa saída;
o manifesto inclui hashes dos artefatos. Versão e métodos também ficam nos
registros de futuras tentativas (`aplicador_versao`, `correspondencias_aplicacao`).

## Replay manual

Sempre use saída nova:

```bash
docker compose run --rm tcc python scripts/experimento/replay_ancoras.py \
  --execucao outputs/campanha_docker/AMP_PAINEL_20261019T181245Z_1aca0df2 \
  --checkout-parser workspace/wt-1 \
  --saida outputs/revalidacoes/ANCORAS_INDENTACAO_V2
```

O comando diagnostica a aplicação, sem gerar novas respostas, executar o alvo
ou anexar tentativas ao experimento original. O replay não atribui R/F/M nem
transforma as oito correções em aceites.

## Próxima execução

Inicie uma execução nova pelo painel. O código montado no Docker será carregado
pelo novo processo; não é preciso reconstruir a imagem. Retomar a saída antiga
com a implementação modificada deve ser recusado pelo contrato científico.

Os problemas de F nos testes que exigem trusted HTML são independentes e não
foram alterados nesta entrega.
