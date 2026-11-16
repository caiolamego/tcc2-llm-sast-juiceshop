---
schema_versao: '1.0'
categoria: security_misconfiguration
versao_documento: '1.1'
status: PRONTO
fontes:
- titulo: 'CWE-200: Exposure of Sensitive Information'
  url: https://cwe.mitre.org/data/definitions/200.html
  consultado_em: '2026-10-13'
- titulo: Denial of Service Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: 'CWE-548: Exposure of Information Through Directory Listing'
  url: https://cwe.mitre.org/data/definitions/548.html
  consultado_em: '2026-11-03'
- titulo: 'Express: serve-index'
  url: https://expressjs.com/en/resources/middleware/serve-index.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-1333: Inefficient Regular Expression Complexity'
  url: https://cwe.mitre.org/data/definitions/1333.html
  consultado_em: '2026-11-03'
- titulo: Regular expression Denial of Service - ReDoS
  url: https://community.owasp.org/attacks/Regular_expression_Denial_of_Service_-_ReDoS
  consultado_em: '2026-11-03'
- titulo: 'MDN: Regular expressions'
  url: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

Configuração pode expor dados e arquivos ou permitir consumo excessivo de recursos. Listagem de diretórios, erros detalhados, desserialização e expressões regulares não são o mesmo mecanismo. Sinais: `serveIndex`, resposta com objeto inteiro, `new RegExp` com valor variável e padrões com repetição aninhada.

## 2. Origem e condições

Verifique o conteúdo realmente acessível, a exposição da rota e limites anteriores. Uma expressão problemática só causa indisponibilidade se entradas suficientemente grandes chegam ao processamento. Em expressão montada com variável, confira se o valor é externo: a variável pode ser interna ao código.

## 3. Impactos e interpretação

Os efeitos incluem divulgação e negação de serviço. Um identificador amplo de exposição de dados não determina sozinho sensibilidade, destinatário ou exploração. Uma listagem revela nomes, datas e estrutura, mesmo quando cada arquivo já é público.

## 4. Mitigação por mecanismo

### Exposição
Delimite diretórios públicos e campos de respostas, mantenha arquivos internos fora da raiz servida e evite listar conteúdo desnecessário.
### Listagem de diretórios
Desative a listagem quando ela não for função do produto. `serveIndex` gera a página com os nomes; `express.static` entrega o conteúdo. Retirar o primeiro esconde os nomes e mantém os arquivos acessíveis por URL direta.

Alternativa: quando a listagem é necessária, aponte para uma pasta pública específica, exija autorização na rota, use `filter` para mostrar só o permitido e mantenha `hidden` desligado. Inadequado: esconder o link na interface, pois a rota continua respondendo; apagar a rota de arquivos, pois quebra o download.
### ReDoS e recursos
Evite padrões com backtracking excessivo e limite tamanho/trabalho; um timeout de rede não interrompe necessariamente CPU síncrona no event loop. Reescreva repetições aninhadas, como `(a+)+`. Não use entrada externa como padrão: se ela representa texto, compare com `includes` ou escape os caracteres especiais antes de `new RegExp`.

Alternativa: motor de expressão regular sem backtracking, quando o usuário precisa fornecer padrões. Inadequado: `try/catch` em volta do `test`, pois o padrão lento não lança erro; filtrar alguns caracteres, pois o restante continua sendo interpretado.
### Desserialização
Use formatos de dados e schemas conhecidos. Não reconstrua código ou objetos executáveis a partir de dados não confiáveis. Limites não tornam execução arbitrária segura.

## 5. Preservação funcional

Preserve arquivos públicos necessários e campos contratados. Limites devem acomodar entradas legítimas e produzir as respostas esperadas. Não silencie todos os erros nem remova endpoints indiscriminadamente. Ao tirar uma listagem, mantenha o download dos arquivos. Ao escapar um padrão, confira se o código dependia de curingas: nesse caso, a busca precisa de outra regra, não de texto literal.

## 6. Exemplo genérico

Vulnerável como seleção de dados públicos:
```typescript
const publicProfile = { ...account };
```
Projeção explícita (contrato público ilustrativo):
```typescript
const publicProfile = { displayName: account.displayName, avatar: account.avatar };
```
Listagem exposta junto com os arquivos:
```typescript
app.use('/arquivos', express.static('publico/arquivos'), serveIndex('publico/arquivos'));
```
Sem listagem, com o download preservado:
```typescript
app.use('/arquivos', express.static('publico/arquivos'));
```
Listagem necessária, restrita por autorização e por filtro:
```typescript
const permitido = (nome: string) => /\.(csv|txt)$/.test(nome);
app.use('/arquivos', exigirAutorizacao, express.static('publico/arquivos'),
  serveIndex('publico/arquivos', { filter: permitido }));
```
Entrada externa usada como padrão:
```typescript
const padrao = new RegExp(String(req.query.termo));
const achados = nomes.filter((nome) => padrao.test(nome));
```
Busca por texto literal, com tamanho limitado:
```typescript
const termo = String(req.query.termo ?? '').slice(0, 100);
const achados = nomes.filter((nome) => nome.includes(termo));
```
Quando a expressão regular é necessária, com o valor escapado:
```typescript
const escapar = (texto: string) => texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const padrao = new RegExp(escapar(termo));
```

## 7. Limitações e verificação

Os exemplos dependem de quais campos e pastas são públicos. Verifique resposta real, logs e arquivos. Teste a pasta sem o arquivo no caminho, arquivos ocultos e download direto. Para recursos, faça testes com limites e padrões adversariais, como `(a+)+$` e entradas longas terminadas em caractere inválido. `RegExp.escape` existe, mas depende da versão do ambiente. Não conclua segurança por ausência de um alerta.
