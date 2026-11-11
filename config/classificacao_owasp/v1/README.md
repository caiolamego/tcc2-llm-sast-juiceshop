# Classificação OWASP complementar v1

Configuração usada somente na consolidação offline, posterior às campanhas de
06/11/2026. O catálogo original continua sendo a entrada científica da campanha;
esta tabela não modifica os prompts, o RAG, as avaliações ou a identidade dos casos.

`classificacao-78-casos.csv` preserva 29 associações originais e acrescenta 49:
41 correspondências explícitas com as listas de CWE da OWASP 2025 e oito decisões
contextuais. `owasp_por_cwe` e `owasp_2025_analise` distinguem taxonomia e contexto.

Os quatro CWE-943 foram associados a A05 pelo contexto de consultas NoSQL.
O caso em `chat.ts` permanece falso positivo. Quatro CWE-20 foram agrupados pelo
mecanismo: propriedade do carrinho em A01, restrições de nota/quantidade em A06,
e cadastro/estabelecimento de credenciais em A07. As justificativas e os trechos
estão em `decisoes-contextuais.json` e `revisao-contextual.json`.

As fontes OWASP estão em `fontes-owasp/`, no commit oficial
`3a31f35346c3f4e90f350395124382fa53af2afe`, com autoria e licença registradas.
O manifesto desta configuração fixa hashes de todos os dados usados e do catálogo.
O leitor recusa população divergente, IDs duplicados, alteração de categoria
original, divergência da triagem e arquivos com hash alterado.

A classificação descreve a família do alerta. Não confirma explorabilidade,
não reclassifica integralmente os 29 rótulos originais e não constitui revisão
humana independente. Permanecem 55 rótulos confirmados, 21 falsos positivos e
dois inconclusivos. As decisões contextuais podem ser revistas em nova versão,
com nova consolidação derivada, sem repetir a geração de correções.

Distribuição dos 78 casos: A01=26, A02=3, A04=5, A05=22, A06=12, A07=7, A08=3.
Não há casos atribuídos a A03, A09 ou A10 nesta partição; isso não demonstra
ausência dessas falhas na aplicação.
