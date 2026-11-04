---
schema_versao: '1.0'
categoria: injection
versao_documento: '1.1'
status: PRONTO
fontes:
- titulo: SQL Injection Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: NoSQL Security Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/NoSQL_Security_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: XML External Entity Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: 'Node.js: VM'
  url: https://nodejs.org/api/vm.html
  consultado_em: '2026-10-13'
- titulo: 'CWE-95: Eval Injection'
  url: https://cwe.mitre.org/data/definitions/95.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-134: Use of Externally-Controlled Format String'
  url: https://cwe.mitre.org/data/definitions/134.html
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

Injeção ocorre quando um valor vira instrução. SQL, seletores NoSQL, comandos, código dinâmico, templates e XML possuem interpretadores diferentes; localizar o interpretador é o primeiro passo. Sinais: consulta concatenada, `eval`, `new Function`, `$where`, filtro que recebe objeto do cliente, parser XML com entidades ativas e texto externo no primeiro argumento de função de formatação.

## 2. Origem e condições

Acompanhe entrada, transformações e chamada final. Um literal interno ou um valor validado pode tornar o padrão apenas suspeito. Dados de banco também podem ter origem externa. A confirmação depende da possibilidade de controlar a sintaxe interpretada.

## 3. Impactos e interpretação

O efeito pode ser acesso indevido, modificação de dados ou execução de instruções. Encontrar concatenação não estabelece explorabilidade; verificar o driver e suas opções é necessário.

## 4. Mitigação por mecanismo

### SQL
Use parâmetros para valores; nomes de tabelas e ordenações requerem seleção de identificadores permitidos.

Alternativa: consulta estruturada do ORM, sem texto montado. Inadequado: escapar aspas à mão ou bloquear palavras como `SELECT`.
### NoSQL
Construa seletores com campos conhecidos e valores escalares validados; receber um objeto inteiro permite operadores inesperados mesmo sem texto concatenado. Confira o tipo antes de montar o filtro. Não aceite operadores vindos do cliente, como `$where`, `$regex` e `$expr`. Troque `$where` por operadores padrão de consulta, pois ele executa JavaScript no banco.

Alternativa: lista de operadores permitidos, quando o filtro precisa ser flexível. Inadequado: procurar `$` no texto da requisição, o que rejeita strings legítimas e não valida tipos; confiar só em controles de rede.
### Código, comandos e templates
Prefira operações declarativas e argumentos separados. Não execute código recebido. A correção principal é refatorar para não precisar de `eval`. Para dados, use um parser como `JSON.parse`. Para escolhas, mapeie valores permitidos para funções conhecidas. Um contexto de `node:vm` não constitui fronteira de segurança. Escaping de template depende do contexto de saída.

Alternativa: interpretador de gramática restrita, quando o produto precisa avaliar expressões. Inadequado: filtrar palavras ou caracteres antes do `eval`.
### XML
Desabilite DTDs quando possível e rejeite `DOCTYPE`. Se forem necessários, desligue entidades externas e carregamento externo, e limite a expansão. Substituir aspas não resolve XXE. Trate opção de segurança não suportada como falha, sem seguir com proteção parcial.
### Strings de formato
Strings de formato devem ser constantes quando o interpretador as trata como instruções. Passe valores externos como argumentos. Em JavaScript, o efeito é alterar a mensagem e os argumentos consumidos, sem escrita em memória.

## 5. Preservação funcional

Mantenha filtros, ordenação, mensagens e resultado esperado. Não remova a consulta ou a função para eliminar o alerta. Verifique valores válidos que contêm aspas e caracteres internacionais. Ao substituir `eval` ou `$where`, confira que os formatos aceitos hoje e o conjunto de resultados continuam iguais, inclusive para IDs numéricos e para mais de um resultado.

## 6. Exemplo genérico

Exemplo SQL vulnerável (API abstrata de driver):
```typescript
const sql = "SELECT title FROM notes WHERE owner = '" + owner + "'";
await db.query(sql);
```
Versão com parâmetros, assumindo suporte a placeholders nesse driver:
```typescript
await db.query('SELECT title FROM notes WHERE owner = ?', [owner]);
```
NoSQL: valor do corpo usado como filtro. Um objeto como `{ "$ne": "" }` vira operador:
```typescript
const pedidos = await colecao.find({ dono: req.body.dono }).toArray();
```
Tipo conferido antes da consulta:
```typescript
if (typeof req.body.dono !== 'string') return res.status(400).send('Dono inválido');
const pedidos = await colecao.find({ dono: { $eq: req.body.dono } }).toArray();
```
NoSQL: JavaScript montado com entrada, trocado por operador padrão:
```typescript
await colecao.find({ $where: `this.codigo == '${codigo}'` }).toArray();

await colecao.find({ codigo: String(codigo) }).toArray();
```
Código: texto avaliado, trocado por parser e por mapa de operações:
```typescript
const dados = eval('(' + texto + ')');
const resultado = eval(`${a} ${req.body.operador} ${b}`);

const OPERACOES = new Map([
  ['+', (x: number, y: number) => x + y],
  ['*', (x: number, y: number) => x * y],
]);
const dados = JSON.parse(texto);
const operacao = OPERACOES.get(req.body.operador);
if (!operacao) return res.status(400).send('Operador inválido');
const resultado = operacao(a, b);
```
XML: opções de um parser abstrato; os nomes variam por biblioteca:
```typescript
const doc = parser.parse(texto, { expandirEntidades: true, carregarDtd: true });

const doc = parser.parse(texto, { expandirEntidades: false, carregarDtd: false });
```
Formato: valor externo concatenado à string de formato, depois passado como argumento:
```typescript
console.error('Falha ao ler ' + nome + ': %s', erro.message);

console.error('Falha ao ler %s: %s', nome, erro.message);
```

## 7. Limitações e verificação

A sintaxe dos parâmetros varia entre drivers. Teste dados hostis e válidos, tipos e erro de banco. Envie objeto no lugar de string, `DOCTYPE` com entidade externa e `%s` em nomes. Cada exemplo vale para o seu mecanismo: nenhum prova uma mitigação universal.
