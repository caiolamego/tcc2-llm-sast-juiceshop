# Rodada 12 — validação e meta de 50 desafios

As quatro etapas foram executadas: integração HTTP com banco, scan completo,
repetição equivalente e revisão/publicação da matriz. Nenhuma LLM executada.

| Perfil exploratório acumulado | Rodada 11 | Rodada 12 |
|---|---:|---:|
| Alertas brutos | 76 | 78 |
| Confirmados pela revisão | 53 | 55 |
| Falsos positivos | 21 | 21 |
| Inconclusivos | 2 | 2 |
| Desafios distintos confirmados | 47 | 50 |

Perfis somados: default, custom-rules e rodadas 2–12. A matriz mantém 113
chaves únicas e scans históricos sobrepostos: suas 109 observações não são
109 vulnerabilidades distintas. A condição same-site de JSONP da rodada 11
continua válida; atingir 50 não elimina precondições dos casos anteriores.

## Três candidatos confirmados

| Desafio | Mecanismo demonstrado | Controle testado |
|---|---|---|
| `emptyUserRegistration` | Omitir passwordRepeat contorna a condição conjunta do middleware; email e senha vazios chegam à API gerada e persistem. | Obrigatoriedade e conteúdo não vazio retornam 400 e não criam registro. |
| `passwordRepeatChallenge` | Com todos os campos presentes, o middleware faz trim mas não compara as senhas; confirmação divergente persiste usuário. | Comparação bloqueia divergência e aceita cadastro válido. |
| `zeroStarsChallenge` | Rating INTEGER e allowNull false não impõem mínimo; POST com CAPTCHA válido persiste zero. | Intervalo 1–5 bloqueia zero e aceita 3; CAPTCHA incorreto continua rejeitado. |

A regra de cadastro aponta `server.ts:409–418` e tem duas associações
confirmadas após revisão dos modelos, hooks e API. Não há regra baseada
em nome de desafio ou interpretação do hook como proteção. O hook apenas
registra o desafio e chama next. A regra de rating aponta a definição do
campo em `models/feedback.ts:57–66`.

Dois alertas novos correspondem a três desafios. Isso não é uma estimativa
de três causas ou patches independentes: as validações de cadastro podem
ser corrigidas conjuntamente. Confirmar desafios de validação não implica
atribuir gravidade alta ou demonstrar invasão de conta. A severidade e a
utilidade de cada caso para o experimento devem ser revisadas na consolidação.

## Testes e limites

O harness reutiliza a estrutura de integração da rodada 8, sem modificar
seus arquivos ou resultados. Executa HTTP em 127.0.0.1, Express 4.22.1,
Finale 1.2.2, Sequelize 6.37.3 e sqlite3 5.1.7, com SQLite em memória.
Modelos User/Feedback/Captcha, middlewares de cadastro/CAPTCHA e chamada
Finale resource são extraídos do commit real. Cada sucesso é conferido no
banco, não apenas pelo status HTTP. Controles protegidos pertencem ao teste,
não são alterações no Juice Shop.

Identidade, sanitização, hash, hooks e criação de carteira são simulados.
Não é servidor completo, teste de login ou de qualidade criptográfica.
Associações completas entre modelos não são reconstruídas; os casos não
dependem de chaves estrangeiras. Dependências e lockfile do ambiente isolado
foram arquivados; o alvo não possui lockfile. Node usado: 24.14.0.

As regras são heurísticas de baixa confiança. Controle externo pode gerar
falso positivo, documentado nos fixtures; um bloco validate pode conter uma
validação insuficiente e ainda assim não ser detectado. Ausência de alerta
não comprova segurança. Cada associação confirmada depende de revisão e
teste, não só de correspondência do padrão.

Verificações: três cenários HTTP aprovados (quatro entradas TAP contando o
agrupador), 48 testes Python aprovados, checks de hashes e equivalência dos
scans. Semgrep 1.177.0 com timeout de 30 segundos, mesmas exclusões e commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f`. Os dois scans retornaram os mesmos
dois achados, sem erros/timeouts reportados. Os exemplos de regras passaram.

## Artefatos e reprodução

- [Matriz CSV](../outputs/auditoria_sast/rodada12/matriz_desafios.csv) e JSON no mesmo diretório.
- [Resumo antes/depois](../outputs/auditoria_sast/rodada12/resumo.json).
- [Triagem](../config/auditoria_desafios_rodada12.yaml).
- [Scan](../outputs/auditoria_sast/rodada12.json) e [manifesto](../outputs/auditoria_sast/manifesto-rodada12.json).
- [Repetição](../outputs/auditoria_sast/rodada12/repeticao/rodada12.json).
- [Testes TAP](../outputs/auditoria_sast/rodada12/testes/testes.tap), manifesto e dependências no mesmo diretório.

Da raiz do repositório, usando o commit limpo e Semgrep 1.177.0:

```bash
npm ci --prefix outputs/auditoria_sast/rodada12/testes/dependencias --no-audit --no-fund
JUICE_SHOP_WORKTREE=/caminho/juice-shop ROUND12_DEPS="$PWD/outputs/auditoria_sast/rodada12/testes/dependencias" node --test scripts/test_rodada12_flows.mjs
semgrep --test --config rules rules
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/scan_semgrep_exploratorio.py --worktree /caminho/juice-shop --perfis rodada12 --timeout 30 --saida /caminho/novo-scan
```

`verify_rodada12.py --worktree ... --deps ... --saida ...` arquiva outra
execução e recusa sobrescrever evidências existentes. Para regenerar a matriz:

```bash
audit_args=()
for round in 2 3 4 5 6 7 8 9 10 11 12; do
  scan_path="outputs/auditoria_sast/rodada${round}.json"
  if [ "$round" = 6 ] || [ "$round" = 9 ]; then
    scan_path="outputs/auditoria_sast/rodada${round}/scan_completo/rodada${round}.json"
  fi
  audit_args+=(--scan-extra "rodada${round}=${scan_path}" --triagem-extra "config/auditoria_desafios_rodada${round}.yaml")
done
python3 scripts/build_challenge_matrix.py --worktree /caminho/juice-shop "${audit_args[@]}" --revisoes config/revisoes_associacoes_rodada6.yaml --saida /caminho/nova-matriz
python3 scripts/report_rodada12.py
```

## Encerramento

Meta de pelo menos 50 desafios atingida dentro das condições registradas.
Não foi iniciada rodada 13. Baseline JS001–JS012, catálogo antigo de correção,
snapshots anteriores e revisão SSTI permanecem intactos. A seleção versionada
de causas para correção e seus testes de regressão ainda precisam ser
consolidados antes da execução da LLM pelo usuário.
