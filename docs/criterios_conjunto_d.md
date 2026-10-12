# Critérios do conjunto D (testes que dependem da vulnerabilidade)

Escrito em 2026-10-09, **antes** de classificar qualquer teste. A lista de testes vem depois, em `docs/conjunto_d.md`, construída a partir destes critérios aplicados à suíte inteira.

## Definição (pré-registrada, protocolo Seção 7.1)

O conjunto **D** reúne os testes do Juice Shop que falham justamente porque a vulnerabilidade foi corrigida. O conjunto **F** reúne os testes de comportamento funcional. Uma correção não perde `F` por fazer cair um teste de D.

## Regra

Um teste pertence a D **se, e somente se, suas asserções só podem valer enquanto a vulnerabilidade está presente**, verificado por **uma** destas três formas:

**(a) Asserção de desafio resolvido.** O corpo do teste afirma que um desafio foi resolvido, em uma das três variantes encontradas na suíte:
- `assert.equal(challenges.<id>.solved, true)`
- `assert.equal(challenge.solved, true)`
- a mensagem `'Challenge successfully solved'`

**(b) Carga de ataque conhecida com resposta de sucesso.** O teste envia uma carga de ataque conhecida (por exemplo, SQL injection, path traversal, null byte, XXE, injeção NoSQL, token forjado, XSS) e afirma uma resposta de sucesso: status 2xx, token de autenticação, ou dado que não deveria ser acessível sem a falha.

**(c) Evidência de que a carga foi interpretada.** O teste afirma que a resposta contém sinal de que a carga foi interpretada pela aplicação: avaliação de template, vazamento de erro de SQL, ou execução (ou entrega sem neutralização) de script.

**Todo o resto é F.** Em particular:
- **Testes que afirmam que a defesa funciona** ou que a aplicação **não é suscetível** ("is caught by parser", "is not susceptible", "cannot be bypassed", resposta de erro 4xx para a carga, carga neutralizada) **são F**: uma correção não deve quebrá-los.
- **Testes baseados em mock do caminho de chamada são F, não D.** Exemplo: um teste unitário que verifica, por mock, qual caminho foi passado a `res.sendFile`. Ele falha quando a forma da chamada muda, não porque a vulnerabilidade sumiu.
- Testes que **enviam** uma carga de ataque mas só afirmam algo que vale com ou sem a falha (por exemplo, que o servidor não caiu) são F.

## Como aplicar

1. A varredura cobre **`test/api/` e `test/server/` inteiros**, e não os testes que falharam em alguma execução.
2. Para cada `it(...)`, o que conta são as **asserções** do próprio bloco. O nome do teste serve só para localizar candidatos; não decide a classe.
3. Cada teste em D é listado com: arquivo, nome do `it(...)`, critério (a), (b) ou (c), e a linha da asserção que justifica.
4. Casos examinados e rejeitados (que parecem de ataque mas não cumprem nenhum dos três critérios) são listados à parte, com o motivo, para que a fronteira fique auditável.
5. Em dúvida entre D e F, a classe é **F** (conservador: não protege a correção).

## Duas classificações (análise de sensibilidade)

- **`d_marcador`:** só o critério (a). Regra mecânica, sem julgamento.
- **`d_criterio`:** os três critérios, pela lista de `docs/conjunto_d.md`.

As métricas são reportadas nas duas versões.
