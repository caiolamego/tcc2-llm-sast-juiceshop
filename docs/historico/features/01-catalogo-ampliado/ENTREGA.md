# Entrega da feature 01 — Catálogo ampliado

**Data:** 12/10/2026.  
**Resultado:** implementada e validada. Alterações locais, sem commit ou push automático.

## Resultado oficial

- **124 alertas de entrada:** 78 casos incluídos e 46 exclusões.
- Incluídos: **55 confirmados, 21 falsos positivos e 2 inconclusivos**.
- Uma ocorrência por caso, identificada por `AMP` + prefixo de hash; sem agrupamento por causa.
- Severidades incluídas: 69 WARNING, 8 ERROR e 1 INFO.
- 49 casos sem OWASP 2025 mapeado e 32 com categoria RAG `generico`; permanecem incluídos.
- 50 avisos de parsing do scan arquivado registrados nos metadados.

Arquivos: [catálogo](../../../../outputs/catalogos/ampliado_v1/catalogo_issues.json),
[exclusões](../../../../outputs/catalogos/ampliado_v1/exclusoes.json) e
[metadados](../../../../outputs/catalogos/ampliado_v1/catalogo_meta.json).

## Ambiente e preparação

- Python: `3.12.3`.
- PyYAML: `6.0.1`.
- Git: `git version 2.43.0`.
- Plataforma de validação: `Linux-6.14.0-37-generic-x86_64-with-glibc2.39`.
- Semgrep da fonte arquivada: `1.177.0`; não foi executado novamente.

Foi preparado `workspace/catalogo-alvo/` com `git init`, remoto
`https://github.com/caiolamego/juice-shop-tcc.git`, fetch limitado ao commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f` com profundidade 1 e checkout detached.
O checkout foi conferido limpo. Não foram instaladas dependências do Juice Shop,
executados seus testes ou realizadas chamadas à LLM.

O gerador exige checkout existente e não implementa clonagem. Usa somente
biblioteca padrão, Git e PyYAML, sem `.env`.

## Comando oficial

```bash
python3 scripts/experiment/build_expanded_catalog.py   --worktree workspace/catalogo-alvo   --saida outputs/catalogos/ampliado_v1
```

O destino já existe após a entrega e será recusado em nova execução.
Para reproduzir, escolher outra saída inexistente; não remover ou sobrescrever a saída oficial.

## Evidências de validação

- `make test-unit`: **73 testes passaram**, sendo 22 da feature e 51 preexistentes.
- Duas gerações reais em destinos diferentes produziram os três arquivos byte a byte idênticos.
- A segunda geração foi executada a partir de diretório temporário externo ao repositório.
- Os testes também verificaram geração em duas cópias do mesmo checkout, com caminhos diferentes.
- Foram conferidos os hashes dos **270 arquivos históricos** de `outputs/` existentes antes da geração; nenhum mudou.
- Foram verificados erros de proveniência, caminhos, encoding, tipo, contagem, identidade,
  destino existente, lock, falha de escrita e mudanças nas fontes durante a geração.
- Fontes excluídas não são lidas para extrair código; não há snippets de codefixes nas exclusões.
- `git diff --check` passou.

### SHA-256 das saídas

| Artefato | SHA-256 |
|---|---|
| `catalogo_issues.json` | `08672899e712fbeef2070f01c58b5867e080e74f716ddc7d8fd10c6d58344aee` |
| `catalogo_meta.json` | `f44e6dc43eb2a0ef8d12a19b2ed1c0a223b647129fdd618fb4dd053090f47979` |
| `exclusoes.json` | `fabae58fc87ab09978d483962a913db7ce928d1ebe80f54feaf9ab02a309b6c9` |

Os hashes das sete entradas e dos arquivos de código lidos estão em `catalogo_meta.json`.
Os metadados são determinísticos; informações variáveis de ambiente/data ficam neste relatório.

## Limites e próximo passo

A identidade descreve a ocorrência no commit original e não é um algoritmo de correspondência após patches.
O perfil remoto histórico ainda precisa ser congelado para novas análises.
O pipeline continua utilizando JS001–JS012 e os rulesets antigos: o novo catálogo ainda não é consumido pelo orquestrador.
A próxima feature deve integrar seleção de catálogo, schema, regras ampliadas e comparação de R/M.
