# Regras locais do Semgrep

As regras estão organizadas pela rodada da auditoria em que foram introduzidas:

- `rodada1/`: bypass de sanitização Angular, atualização MongoDB com entrada não confiável e allowlist de redirecionamento por substring.
- `rodada2/` a `rodada12/`: regras acrescentadas nas respectivas rodadas.

Cada arquivo `.yaml` define uma regra; o `.ts` de mesmo nome contém os casos de teste do Semgrep. Os números das rodadas indicam a origem das regras, não casos de correção ou estratégias de prompt.

Para verificar as regras:

```bash
semgrep scan --test rules
```

Os perfis `angular-sanitizer-bypass` e `custom-rules` do script `scripts/scan_semgrep_exploratorio.py` continuam com os mesmos nomes e agora usam `rodada1/`.

Os artefatos históricos em `outputs/` preservam os caminhos originais. O classificador do scan combinado resolve caminhos antigos `rules/<arquivo>.yaml` para `rules/rodada1/<arquivo>.yaml` quando necessário e continua conferindo o hash do conteúdo. A reorganização não altera o conteúdo nem os IDs das regras.
