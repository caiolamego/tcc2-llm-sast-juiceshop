---
schema_versao: '1.0'
categoria: path_traversal
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: 'CWE-22: Improper Limitation of a Pathname to a Restricted Directory'
  url: https://cwe.mitre.org/data/definitions/22.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-73: External Control of File Name or Path'
  url: https://cwe.mitre.org/data/definitions/73.html
  consultado_em: '2026-11-03'
- titulo: Path Traversal
  url: https://community.owasp.org/attacks/Path_Traversal
  consultado_em: '2026-11-03'
- titulo: 'Node.js: Path'
  url: https://nodejs.org/api/path.html
  consultado_em: '2026-11-03'
- titulo: 'Express: Response (res.sendFile)'
  url: https://expressjs.com/en/5x/api/response
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

Uma entrada externa define, no todo ou em parte, o nome ou o caminho de um arquivo que a aplicação lê, grava, serve ou remove. Sinais: `res.sendFile`, `res.download`, `fs.readFile`, `fs.createReadStream` e `fs.writeFile` recebendo valor de rota, consulta, corpo ou cabeçalho, inclusive depois de `path.join` ou `path.resolve`.

## 2. Origem e condições

Rastreie de onde vem o nome e se ele alcança a operação sem ficar restrito ao diretório esperado. `path.join` normaliza `..`, mas não confina o resultado. Em `path.resolve`, um argumento absoluto descarta tudo o que está à sua esquerda. `path.isAbsolute` só examina o texto e não mitiga traversal. Considere variações como `..\`, `%2e%2e%2f`, codificação dupla e byte nulo, e decodifique uma única vez, antes de validar. Valor fixo ou vindo de lista do servidor não caracteriza a falha.

## 3. Impactos e interpretação

A falha pode expor configuração, segredos e código, ou sobrescrever arquivos quando a operação é de escrita. Um alerta sobre caminho não literal não prova que a raiz é ultrapassada: confira se uma camada anterior já restringe o valor.

## 4. Mitigação por mecanismo

### Mapeamento
Quando o conjunto de arquivos é conhecido, receba um identificador e converta-o no servidor; rejeite o restante.
### Validação do nome
Prefira uma lista do que é aceito: caracteres permitidos, sem separadores de diretório, um único ponto e extensões conhecidas. Remover `../` é frágil, pois a própria remoção pode criar uma nova sequência.
### Confinamento à raiz
Resolva o caminho absoluto e compare com a raiz usando `path.relative`. Verificar um prefixo de texto é insuficiente, inclusive porque `/dados/app-privado` começa com `/dados/app`.
### Opção do framework
Em `res.sendFile`, a opção `root` recebe a raiz absoluta, e o Express valida que o caminho relativo permanece dentro dela. Sem `root`, a construção do caminho absoluto precisa ser segura por si.
### Links simbólicos e privilégios
Se houver links na raiz, use `fs.realpath` e compare o caminho real. Execute com o menor privilégio possível e não revele caminhos em mensagens de erro.

## 5. Preservação funcional

Mantenha acessíveis os arquivos legítimos, incluindo subpastas e nomes com espaços, quando a rota já os aceita: reduzir a entrada a `path.basename` pode quebrar esse uso. Preserve a raiz servida, a rota, os tipos de arquivo e o tratamento de erro existente. Trate a recusa pelo mesmo caminho das outras falhas da rota.

## 6. Exemplo genérico

Caminho montado com o parâmetro recebido:
```typescript
app.get('/docs/:nome', (req, res) => {
  res.sendFile(path.join(__dirname, 'docs', req.params.nome));
});
```
Confinamento delegado ao framework, com a raiz separada do nome:
```typescript
const RAIZ_DOCS = path.resolve(__dirname, 'docs');

app.get('/docs/:nome', (req, res, next) => {
  res.sendFile(req.params.nome, { root: RAIZ_DOCS }, (erro) => {
    if (erro) next(erro);
  });
});
```
Comparação explícita, para operações que não oferecem `root`:
```typescript
const alvo = path.resolve(RAIZ_DOCS, nome);
const relativo = path.relative(RAIZ_DOCS, alvo);
const dentro = relativo !== '' && relativo !== '..' &&
  !relativo.startsWith('..' + path.sep) && !path.isAbsolute(relativo);
if (!dentro) throw new Error('Caminho fora da raiz');
```

## 7. Limitações e verificação

Os exemplos supõem uma raiz fixa e não tratam links simbólicos. Teste nomes válidos, subpastas, `../`, `..\`, formas codificadas, caminhos absolutos e nomes inexistentes. Confinar à raiz não decide quem pode ler cada arquivo: autorização continua sendo outra verificação.
