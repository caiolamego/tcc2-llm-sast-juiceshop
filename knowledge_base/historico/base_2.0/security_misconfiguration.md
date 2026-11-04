---
schema_versao: '1.0'
categoria: security_misconfiguration
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: 'CWE-200: Exposure of Sensitive Information'
  url: https://cwe.mitre.org/data/definitions/200.html
  consultado_em: '2026-10-13'
- titulo: Denial of Service Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Configuração pode expor dados e arquivos ou permitir consumo excessivo de recursos. Listagem de diretórios, erros detalhados, desserialização e expressões regulares não são o mesmo mecanismo.

## 2. Origem e condições

Verifique o conteúdo realmente acessível, a exposição da rota e limites anteriores. Uma expressão problemática só causa indisponibilidade se entradas suficientemente grandes chegam ao processamento.

## 3. Impactos e interpretação

Os efeitos incluem divulgação e negação de serviço. Um identificador amplo de exposição de dados não determina sozinho sensibilidade, destinatário ou exploração.

## 4. Mitigação por mecanismo

### Exposição
Delimite diretórios públicos e campos de respostas, mantenha arquivos internos fora da raiz servida e evite listar conteúdo desnecessário.
### ReDoS e recursos
Evite padrões com backtracking excessivo e limite tamanho/trabalho; um timeout de rede não interrompe necessariamente CPU síncrona no event loop.
### Desserialização
Use formatos de dados e schemas conhecidos. Não reconstrua código ou objetos executáveis a partir de dados não confiáveis. Limites não tornam execução arbitrária segura.

## 5. Preservação funcional

Preserve arquivos públicos necessários e campos contratados. Limites devem acomodar entradas legítimas e produzir as respostas esperadas. Não silencie todos os erros nem remova endpoints indiscriminadamente.

## 6. Exemplo genérico

Vulnerável como seleção de dados públicos:
```typescript
const publicProfile = { ...account };
```
Projeção explícita (contrato público ilustrativo):
```typescript
const publicProfile = { displayName: account.displayName, avatar: account.avatar };
```

## 7. Limitações e verificação

O exemplo depende de quais campos são públicos. Verifique resposta real, logs e arquivos. Para recursos, faça testes com limites e padrões adversariais; não conclua segurança por ausência de um alerta.
