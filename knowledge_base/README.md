# Base documental 1.0

Dez documentos em português com exemplos genéricos de JS/TS. Fontes primárias específicas, consultadas em 13/10/2026, estão no frontmatter; somente o corpo é enviado ao prompt. As associações do índice contextualizam a análise e não confirmam vulnerabilidades. Não incorporam soluções do alvo ou resultados de tentativas.

A seleção usa a primeira CWE mapeada, depois a categoria original e por último o documento genérico. Toda recuperação valida novamente os dez documentos e o manifesto, sem rede ou cache persistente.

```bash
.venv/bin/python scripts/experiment/validate_knowledge_base.py
# Publicação inicial, somente se manifesto.json ainda não existir:
.venv/bin/python scripts/experiment/validate_knowledge_base.py --publicar-manifesto
```

A validação padrão é somente leitura. Nunca sobrescrever o manifesto publicado: uma revisão exige nova versão declarada e arquivamento explícito da anterior. Cada documento PRONTO possui sete seções, exemplos vulnerável/corrigido e corpo entre 1 e 20.000 caracteres, sem truncamento. Mudanças de texto, índice, fontes ou versões invalidam os hashes e a retomada RAG na saída existente.

README não é enviado nem integra o manifesto. Datas das fontes são editoriais fixas; o manifesto não contém timestamps de execução ou caminhos absolutos. Testes automatizados não consultam as fontes.
