---
schema_versao: '1.0'
categoria: injection
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: SQL Injection Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: NoSQL Security Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/NoSQL_Security_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: XML External Entity Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: 'Node.js: VM'
  url: https://nodejs.org/api/vm.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Injeção ocorre quando um valor vira instrução. SQL, seletores NoSQL, comandos, código dinâmico, templates e XML possuem interpretadores diferentes; localizar o interpretador é o primeiro passo.

## 2. Origem e condições

Acompanhe entrada, transformações e chamada final. Um literal interno ou um valor validado pode tornar o padrão apenas suspeito. Dados de banco também podem ter origem externa. A confirmação depende da possibilidade de controlar a sintaxe interpretada.

## 3. Impactos e interpretação

O efeito pode ser acesso indevido, modificação de dados ou execução de instruções. Encontrar concatenação não estabelece explorabilidade; verificar o driver e suas opções é necessário.

## 4. Mitigação por mecanismo

### SQL
Use parâmetros para valores; nomes de tabelas e ordenações requerem seleção de identificadores permitidos.
### NoSQL
Construa seletores com campos conhecidos e valores escalares validados; receber um objeto inteiro permite operadores inesperados mesmo sem texto concatenado.
### Código, comandos e templates
Prefira operações declarativas e argumentos separados. Não execute código recebido. Um contexto de `node:vm` não constitui fronteira de segurança. Escaping de template depende do contexto de saída.
### XML e formatos
Desabilite entidades externas e resolução de recursos conforme o parser. Substituir aspas não resolve XXE; strings de formato devem ser constantes quando o interpretador as trata como instruções.

## 5. Preservação funcional

Mantenha filtros, ordenação, mensagens e resultado esperado. Não remova a consulta ou a função para eliminar o alerta. Verifique valores válidos que contêm aspas e caracteres internacionais.

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

## 7. Limitações e verificação

A sintaxe dos parâmetros varia entre drivers. Teste dados hostis e válidos, tipos e erro de banco. Para NoSQL/XML/código, analise o mecanismo correspondente: o exemplo SQL não prova uma mitigação universal.
