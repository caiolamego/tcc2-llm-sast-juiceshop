// Leitura sintática somente: não importa nem executa o código analisado.
const fs = require('node:fs');
const ts = require(process.argv[2]);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
function inspect(text) {
  const kind = input.path.endsWith('.tsx') ? ts.ScriptKind.TSX : input.path.endsWith('.jsx') ? ts.ScriptKind.JSX : ts.ScriptKind.TS;
  const source = ts.createSourceFile(input.path, text, ts.ScriptTarget.Latest, true, kind);
  if (source.parseDiagnostics.length) return {erro: 'sintaxe_invalida', tokens: [], chamadas: []};
  const byte = n => Buffer.byteLength(text.slice(0, n), 'utf8');
  const tokens = [], chamadas = [], scopes = [];
  function header(node) {
    const end = node.body ? node.body.getStart(source) : node.end;
    return text.slice(node.getStart(source), end).replace(/\s+/g, ' ').trim();
  }
  function label(node) {
    if (node.name) return `${ts.SyntaxKind[node.kind]}:${node.name.getText(source)}:${header(node)}`;
    const p = node.parent;
    if (ts.isVariableDeclaration(p) || ts.isPropertyAssignment(p)) return `atribuicao:${p.name.getText(source)}:${header(node)}`;
    if (ts.isReturnStatement(p)) return `retorno:${header(node)}`;
    if (ts.isCallExpression(p)) return `callback:${p.expression.getText(source)}:${p.arguments.indexOf(node)}:${header(node)}`;
    return `anonima:${header(node)}`;
  }
  function visit(node, stack) {
    if (ts.isFunctionLike(node) && node.body) {
      stack = [...stack, label(node)];
      scopes.push(JSON.stringify(stack));
    }
    if (ts.isCallExpression(node)) {
      chamadas.push({inicio: byte(node.getStart(source)), fim: byte(node.end),
        callee_inicio: byte(node.expression.getStart(source)), callee_fim: byte(node.expression.end),
        callee: node.expression.getText(source).replace(/\s+/g, ''),
        escopo: JSON.stringify(stack), aridade: node.arguments.length,
        argumentos: node.arguments.map(a => [byte(a.getStart(source)), byte(a.end)])});
    }
    // O scanner do TS conhece strings, templates, regex e comentários no contexto da AST.
    if (node.getChildCount(source) === 0 && node.kind !== ts.SyntaxKind.EndOfFileToken && node.end > node.getStart(source)) {
      tokens.push({texto: node.getText(source), inicio: byte(node.getStart(source)), fim: byte(node.end)});
    }
    for (const child of node.getChildren(source)) visit(child, stack);
  }
  visit(source, []);
  return {tokens, chamadas, escopos: scopes};
}
process.stdout.write(JSON.stringify({versao: ts.version, antes: inspect(input.antes), depois: inspect(input.depois)}));
