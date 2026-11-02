# Quarto incremento — seed TOTP

Revisão de 02/11/2026 para `AMP44554338d6458933`, em `data/static/users.yml`. O grupo `seed_totp`
acrescenta nove testes independentes em `tests/functional/juice_shop/seed_totp.test.ts`. As versões,
baselines e campanhas anteriores permanecem preservados; não há geração LLM nesta ampliação.

## Resultado verificado

- **72 casos preparados e seis bloqueados**, das mesmas 78 ocorrências (antes: 71/7).
- O caso `AMP44554338d6458933` foi liberado, sem perder casos antes preparados.
- Baseline completo: **46 grupos comparáveis, 544 testes aprovados e seis ignorados**, com compilações
  de servidor e frontend aprovadas. Os ignorados não são contados como executados.
- Os 45 grupos anteriores mantêm identidades, estados e testes obrigatórios aprovados; ambiente
  registrado igual ao do incremento anterior. A comparação está em `comparacao_final_com_v4.json`.
- **8/8 controles negativos detectados**, com restauração dos originais; controle positivo de rotação
  aprovado com os mesmos nove testes; 32 testes unitários da cobertura/executor aprovados.
- Preflight final `AMP_PREFLIGHT_20261102T225419Z_e3c27b80` concluído para **72 casos**, sem tentativas
  de correção ou chamadas à API.

Resumo com o ID liberado e hashes das entradas/evidências:
`outputs/cobertura_funcional/SEED_TOTP_20261102/resumo_bloco_seed_totp.json`.

O comparador retorna código 2 pela presença do grupo adicional e pela identidade ampliada; não houve
diferença funcional nos grupos compartilhados. As seis lacunas restantes são chat, dois casos nos
testes de last-login-ip, teste de app.guard, template de legendas e Grunt. O plano está em
`auditoria_final/plano_testes_adicionais.md` nas evidências. As saídas `baseline`, `auditoria`,
`controles`, `rotacao_positiva` e `preflights` são da primeira verificação, anterior ao reforço do
inventário. A versão final usa `baseline_final`, `auditoria_final`, `controles_finais`,
`rotacao_positiva_final` e `preflights_finais`; os resultados anteriores são preservados como desenvolvimento.

## Contratos avaliados

- Inventário independente das 23 chaves originais de conta; criação das identidades, senhas e papéis
  declarados no arquivo de seed, incluindo contas excluídas. Apagar ou renomear uma chave reprova o teste.
- Persistência do segredo configurado para o usuário identificado pela chave `timo`, sem fixar seu valor.
- Senha incorreta recusada; senha correta produz somente prova temporária para o segundo fator.
- Prova temporária não permite consultar o estado autenticado da conta.
- TOTP atual permite concluir o login; token de sessão identifica a conta correta e permite consultar
  o estado 2FA e a identidade do usuário via HTTP real.
- TOTP incorreto, código fora da janela e ausência de prova do primeiro fator são recusados.

O cliente de teste calcula HMAC-SHA1, contador temporal e truncamento usando `node:crypto`, sem chamar
`otplib` ou o verificador da aplicação. Sua implementação é conferida com os seis vetores SHA1 publicados
no [Apêndice B da RFC 6238](https://www.rfc-editor.org/rfc/rfc6238.html#appendix-B).
Os testes de API controlam somente `Date`; os timers de HTTP permanecem reais. Códigos negativos são
escolhidos fora das três janelas calculadas pelo avaliador para evitar colisões ocasionais.

## Controles e rotação

Oito regressões temporárias devem reprovar testes específicos: remoção/invalidade do segredo no seed,
perda de persistência, bypass do segundo fator, aceitação de código inválido, rejeição do código válido
e aceitação de código expirado, além de perda de uma chave do inventário original. Os controles também
exercitam `data/datacreator.ts`, `routes/login.ts`
e `routes/2fa.ts`, sempre restaurando os bytes originais.

Um controle positivo troca temporariamente o segredo do seed por uma chave pública de teste distinta
e executa a mesma suíte. Os nove testes passaram tanto no original como no seed rotacionado. Isso
comprova que a avaliação não exige preservar o valor exposto. O original foi restaurado. A troca de
fixture não é uma correção de segurança nem entra como tentativa de remediação.

O código executado e seus hashes estão em
`outputs/cobertura_funcional/SEED_TOTP_20261102/ferramentas/provar_rotacao_final.py`; resultados em
`rotacao_positiva_final/rotacao.json`. A avaliação demonstra funcionalidade de login e vínculo do segredo,
sem comprovar armazenamento seguro, resistência a ataques ou proteção completa da autenticação.

## Identidade e reprodução

- Revisão: `config/cobertura_funcional_v5.yaml`.
- Mapa: `config/mapa_testes_relacionados_v6.yaml`, schema `2.0` e política `relacionada_v2` preservados.
- Controles negativos: `config/controles_cobertura_v5.json`.
- Configuração optativa: `config/execucao_cobertura_v5_preflight.yaml`, modo preflight e K=1.
- Evidências: `outputs/cobertura_funcional/SEED_TOTP_20261102/`.
- Imagem: `sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5`.

Os novos testes são F; o conjunto D não foi alterado. Para reproduzir, siga os comandos dos
[incrementos anteriores](cobertura_funcional_v4.md#reprodução-sem-llm), usando os caminhos desta revisão
e saídas inéditas. Execute os controles, baseline e auditoria sequencialmente com o checkout limpo.
O baseline da revisão anterior não substitui o baseline desta revisão.

O controle positivo foi executado assim, na raiz do projeto e com a imagem acima selecionada em
`TCC_DOCKER_IMAGE`:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python \
  outputs/cobertura_funcional/SEED_TOTP_20261102/ferramentas/provar_rotacao_final.py
```

Esse script recusa saída existente. Para uma nova rodada, preserve o script e os resultados originais
e use uma cópia em outra pasta de incremento com os caminhos ajustados; ele registra o hash do próprio
código. Não o execute simultaneamente aos demais comandos que usam a worktree.

O preflight da configuração publicada pode ser conferido sem chamadas à LLM:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_cobertura_v5_preflight.yaml
```

Preflight verifica preparação e identidade; a evidência dos testes funcionais está no baseline.
