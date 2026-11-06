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

**(d) Asserção que fixa o mecanismo apontado pelo alerta (acrescentado em 05/11/2026, antes da execução oficial).** O teste só pode passar enquanto o alerta de um caso específico continuar sem correção: exige a chamada da API insegura, a resposta exposta, o digest de uma chave fixa ou o acesso a um recurso alheio, inclusive como preparação do próprio teste. Esse critério é **ligado aos casos**: o teste é D somente nas tentativas daqueles casos e continua F em todas as outras. Assim, ele segue protegendo o restante da aplicação.

O critério (d) foi criado porque a regra central deste documento (asserções que só valem com a vulnerabilidade presente) não era alcançada pelas formas (a), (b) e (c), e a regra dos mocks deixava em F testes que exigem `bypassSecurityTrustHtml` com `<script>alert("XSS")</script>`. Cada entrada é justificada pela asserção do teste, não pelo resultado de uma tentativa. Lista: `config/conjunto_d_cobertura_v2.json`, chave `por_caso`.

**(e) Teste cuja finalidade é a própria falha (acrescentado em 06/11/2026).** O teste não tem outro objetivo além de afirmar um comportamento que o catálogo aponta como falha ou que só existe por causa dela: alterar um produto sem credencial, devolver a senha, listar diretórios, baixar logs, mostrar erro interno ou avaliar o código enviado pelo cliente. Diferente do (d), esse critério vale em **todos os casos**: se a correção de outro caso também remover a falha, o teste não deve reprovar essa correção. Ele não protege nenhuma função legítima da aplicação.

O critério (e) foi criado depois da campanha completa de 05 e 06/11/2026, descartada, que mostrou correções certas reprovadas por esses testes (por exemplo, a reativação da proteção de `PUT /api/Products/:id`). Inverter o resultado do teste foi rejeitado: uma falha por outro motivo, como o servidor não subir, viraria aprovação, e o teste aprovado em outros casos reprovaria tentativas sem relação com ele. Quando o teste também cobria um comportamento legítimo, esse comportamento passou para `tests/functional/juice_shop/contratos_legitimos.test.ts`, que vale com e sem a falha.

**Todo o resto é F.** Em particular:
- **Testes que afirmam que a defesa funciona** ou que a aplicação **não é suscetível** ("is caught by parser", "is not susceptible", "cannot be bypassed", resposta de erro 4xx para a carga, carga neutralizada) **são F**: uma correção não deve quebrá-los.
- **Testes baseados em mock do caminho de chamada são F, não D.** Exemplo: um teste unitário que verifica, por mock, qual caminho foi passado a `res.sendFile`. Ele falha quando a forma da chamada muda, não porque a vulnerabilidade sumiu. A exceção é o critério (d): o mock exige a própria API insegura apontada pelo alerta.
- Testes que **enviam** uma carga de ataque mas só afirmam algo que vale com ou sem a falha (por exemplo, que o servidor não caiu) são F.

## Como aplicar

1. A varredura cobre **`test/api/` e `test/server/` inteiros**, e não os testes que falharam em alguma execução.
2. Para cada `it(...)`, o que conta são as **asserções** do próprio bloco. O nome do teste serve só para localizar candidatos; não decide a classe.
3. Cada teste em D é listado com: arquivo, nome do `it(...)`, critério (a), (b) ou (c), e a linha da asserção que justifica.
4. Casos examinados e rejeitados (que parecem de ataque mas não cumprem nenhum dos três critérios) são listados à parte, com o motivo, para que a fronteira fique auditável.
5. Em dúvida entre D e F, a classe é **F** (conservador: não protege a correção).

## Duas classificações (análise de sensibilidade)

- **`d_marcador`:** só o critério (a). Regra mecânica, sem julgamento.
- **`d_criterio`:** os critérios (a) a (e), pela lista de `docs/conjunto_d.md` e pelo arquivo versionado do conjunto D.

As métricas são reportadas nas duas versões.
