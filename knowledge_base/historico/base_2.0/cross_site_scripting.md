---
schema_versao: '1.0'
categoria: cross_site_scripting
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Cross Site Scripting Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: 'Angular: Security'
  url: https://angular.dev/best-practices/security
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

XSS surge quando conteúdo controlável é interpretado como markup ou script. Texto, atributo, URL, CSS e código JavaScript possuem contextos de interpretação distintos.

## 2. Origem e condições

Rastreie a origem do valor e a API de renderização. Verifique validação e sanitização existentes. Um literal fixo ou conteúdo estritamente controlado pode gerar alerta sem fluxo explorável.

## 3. Impactos e interpretação

A execução no navegador pode agir com a sessão da vítima. Um bypass de proteção exige investigar quem controla o valor, sem assumir que toda marcação dinâmica é vulnerável.

## 4. Mitigação por mecanismo

### Texto e HTML
Prefira APIs de texto para texto. HTML intencional requer sanitização compatível com a política de elementos permitidos; escaping não equivale a sanitização.
### Outros contextos
Valide esquemas de URLs; aplique encoding apropriado ao destino e evite dados dentro de scripts.
### Angular
Bindings comuns aplicam proteções contextuais. APIs `bypassSecurityTrust...` transferem responsabilidade ao chamador; não as use para confiar automaticamente em conteúdo externo. Uma política CSP é defesa adicional, não reparo de um sink inseguro.

## 5. Preservação funcional

Identifique se o produto exige texto ou markup permitido. Preserve formatação legítima quando necessária sem habilitar scripts. Não elimine a exibição dos dados.

## 6. Exemplo genérico

Vulnerável quando o valor é texto externo:
```typescript
label.innerHTML = input.title;
```
Exibição como texto em elemento comum:
```typescript
label.textContent = input.title;
```

## 7. Limitações e verificação

O exemplo supõe um elemento de texto, não um elemento de script. Teste renderização, caracteres especiais, links e sanitização. A escolha precisa depende do sink e do requisito de apresentação.
