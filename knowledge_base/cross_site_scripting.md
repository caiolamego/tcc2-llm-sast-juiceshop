---
schema_versao: '1.0'
categoria: cross_site_scripting
versao_documento: '1.1'
status: PRONTO
fontes:
- titulo: Cross Site Scripting Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: 'Angular: Security'
  url: https://angular.dev/best-practices/security
  consultado_em: '2026-11-03'
- titulo: 'Pug: Interpolation'
  url: https://pugjs.org/language/interpolation.html
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

XSS surge quando conteúdo controlável é interpretado como markup ou script. Texto, atributo, URL, CSS e código JavaScript possuem contextos de interpretação distintos. Sinais: `innerHTML`, `bypassSecurityTrust...`, `!{}` em Pug e valor montado dentro de `<script>`.

## 2. Origem e condições

Rastreie a origem do valor e a API de renderização. Verifique validação e sanitização existentes. Um literal fixo ou conteúdo estritamente controlado pode gerar alerta sem fluxo explorável.

## 3. Impactos e interpretação

A execução no navegador pode agir com a sessão da vítima. Um bypass de proteção exige investigar quem controla o valor, sem assumir que toda marcação dinâmica é vulnerável.

## 4. Mitigação por mecanismo

### Texto e HTML
Prefira APIs de texto para texto. HTML intencional requer sanitização compatível com a política de elementos permitidos; escaping não equivale a sanitização.

Alternativa: biblioteca de sanitização, como DOMPurify, sem alterar o conteúdo depois de sanitizar. Inadequado: remover `<script>` com expressão regular ou trocar caracteres à mão.
### Outros contextos
Valide esquemas de URLs; aplique encoding apropriado ao destino e evite dados dentro de scripts. Mesmo com encoding, `<script>` continua um contexto perigoso. Coloque o valor em um elemento ou atributo escapado e leia-o com `textContent` ou `getAttribute`. O mesmo vale para HTML montado por concatenação no servidor.
### Angular
Bindings comuns aplicam proteções contextuais. A interpolação `{{ }}` sempre escapa. `[innerHTML]` sem bypass remove partes perigosas, como `<script>`, e mantém conteúdo seguro, como `<b>`. APIs `bypassSecurityTrust...` transferem responsabilidade ao chamador; não as use para confiar automaticamente em conteúdo externo. O bypass só cabe para valor inspecionado, criado por código confiável. Uma política CSP é defesa adicional, não reparo de um sink inseguro.

Alternativa: fora do template, com `ElementRef` ou `document`, use `DomSanitizer.sanitize` com `SecurityContext.HTML`. Inadequado: trocar por outro método `bypassSecurityTrust...`, que mantém a sanitização desligada.
### Templates do servidor
Em Pug, `#{}` escapa o valor e `!{}` não. Use `#{}` para texto. Reserve `!{}` para conteúdo confiável ou já sanitizado.

## 5. Preservação funcional

Identifique se o produto exige texto ou markup permitido. Preserve formatação legítima quando necessária sem habilitar scripts. Não elimine a exibição dos dados. Trocar HTML por texto mostra as tags literalmente: se há formatação legítima, prefira `[innerHTML]` sem bypass. Confira o que a sanitização remove do conteúdo exibido hoje.

## 6. Exemplo genérico

Vulnerável quando o valor é texto externo:
```typescript
label.innerHTML = input.title;
```
Exibição como texto em elemento comum:
```typescript
label.textContent = input.title;
```
Angular: sanitização desligada para conteúdo externo:
```typescript
this.descricao = this.sanitizer.bypassSecurityTrustHtml(item.descricao);
```
Valor entregue ao binding `[innerHTML]="descricao"`, que sanitiza:
```typescript
this.descricao = item.descricao;
```
Fora do template, com o serviço de sanitização:
```typescript
const limpo = this.sanitizer.sanitize(SecurityContext.HTML, item.descricao) ?? '';
this.elemento.nativeElement.innerHTML = limpo;
```
Pug: valor sem escape, depois com escape:
```pug
p !{comentario}

p #{comentario}
```
Pug: valor dentro de `<script>`, depois lido de um elemento escapado:
```pug
script.
  const titulo = '!{titulo}';
```
```pug
h1#titulo #{titulo}
script.
  const titulo = document.getElementById('titulo').textContent;
```

## 7. Limitações e verificação

Os exemplos supõem um elemento de texto, não um elemento de script, e que o tipo do campo aceite `string`. Teste renderização, caracteres especiais, links e sanitização, com `<script>`, `<img onerror>` e formatação legítima. A escolha precisa depende do sink e do requisito de apresentação.
