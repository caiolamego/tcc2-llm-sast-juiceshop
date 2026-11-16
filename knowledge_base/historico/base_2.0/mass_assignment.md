---
schema_versao: '1.0'
categoria: mass_assignment
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Mass Assignment Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-915: Improperly Controlled Modification of Dynamically-Determined Object Attributes'
  url: https://cwe.mitre.org/data/definitions/915.html
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

A aplicação copia campos enviados pelo cliente para um objeto ou registro sem controlar quais podem mudar. O problema também é chamado de autobinding ou object injection. Sinais: `Model.create(req.body)`, `update(req.body)`, `Object.assign(entidade, req.body)`, espalhamento (`{ ...req.body }`) e laços que copiam chaves dinâmicas.

## 2. Origem e condições

Liste as propriedades que o objeto de destino possui, inclusive as que não aparecem no formulário, como papel, saldo, proprietário ou indicadores de privilégio. Verifique se o cliente consegue enviá-las. Se os campos já são selecionados um a um antes da gravação, ou se o esquema rejeita os demais, a falha não se caracteriza.

## 3. Impactos e interpretação

Um campo não previsto, como `isAdmin=true`, pode elevar privilégios, alterar dados sensíveis ou mudar a lógica de execução. O risco depende do que o modelo contém: confira as propriedades reais antes de concluir.

## 4. Mitigação por mecanismo

### Lista de campos permitidos
Copie explicitamente só o que o usuário pode editar. Prefira essa lista a uma lista de bloqueio, em que um campo novo ou esquecido continua gravável.
### Objeto de entrada dedicado
Não vincule a entrada direto à entidade de domínio. Use um tipo ou objeto que contenha apenas os campos editáveis.
### Opções do ORM e do framework
Quando existir, use o recurso de limitar campos da operação, como a opção `fields` do Sequelize.
### Valores definidos pelo servidor
Proprietário, papel e identificadores vêm da sessão ou da regra de negócio, e não do corpo da requisição.

## 5. Preservação funcional

Levante quais campos a operação aceita hoje e mantenha todos os legítimos, inclusive opcionais, e seus valores padrão. Uma lista incompleta quebra a criação ou a atualização sem erro aparente. Preserve o formato da resposta, a validação e o comportamento em atualização parcial: campos ausentes não devem virar `undefined` sobre valores existentes.

## 6. Exemplo genérico

Corpo inteiro aplicado ao registro:
```typescript
app.put('/perfil', async (req, res) => {
  await perfis.update(req.body, { where: { id: req.session.userId } });
  res.sendStatus(204);
});
```
Apenas campos editáveis, com o identificador vindo da sessão:
```typescript
const EDITAVEIS = ['nome', 'bio'] as const;

app.put('/perfil', async (req, res) => {
  const dados = Object.fromEntries(
    EDITAVEIS.filter((campo) => campo in req.body)
      .map((campo) => [campo, req.body[campo]]),
  );
  await perfis.update(dados, { where: { id: req.session.userId } });
  res.sendStatus(204);
});
```

## 7. Limitações e verificação

O exemplo supõe que `nome` e `bio` são os únicos campos editáveis e usa uma API abstrata de repositório. Teste campos legítimos, atualização parcial, campos extras, tipos inesperados e nomes como `__proto__`. Limitar campos não substitui a autorização sobre o objeto e a operação.
