# Validação das rodadas

Todas as rodadas têm a mesma organização: `rodadaN/README.md` e `rodadaN/manifesto.json`. O manifesto registra regras, teste de relatório, integração disponível e fonte histórica. Ele é um inventário, não evidencia que testes foram executados.

As rodadas 7–12 possuem `test.mjs`. As rodadas 1–6 não possuem integração própria implementada; os testes de regras e a revisão do código não são equivalentes à validação dinâmica. Não existem arquivos vazios ou testes que passam artificialmente para esconder essa lacuna.

Há uma entrada comum para todas as rodadas:

```bash
python scripts/auditoria/testar_rodada.py --rodada 7
python scripts/auditoria/testar_rodada.py --rodada 7 --tipo regras
python scripts/auditoria/testar_rodada.py --rodada 7 --tipo relatorio
python scripts/auditoria/testar_rodada.py --rodada 7 --tipo integracao --worktree /caminho/juice-shop
python scripts/auditoria/testar_rodada.py --rodada 8 --tipo integracao --worktree /caminho/juice-shop --deps /caminho/dependencias
```

As variáveis, versões e limites dos testes continuam nos relatórios de `docs/auditoria/`. As rodadas exigem verificações distintas porque investigam mecanismos diferentes. A interface é uniforme, mas a validação de cada mecanismo não pode ser substituída por um teste genérico.

`historico/` preserva os seis arquivos originais byte a byte para conferir os hashes dos manifestos em `outputs/`. Eles são fontes arquivadas, não a entrada atual de execução. As versões em `rodadaN/test.mjs` alteram somente o caminho relativo do catálogo. Os verificadores arquivam o hash da versão atual em novas execuções. Os resultados anteriores não foram modificados nem reexecutados.
