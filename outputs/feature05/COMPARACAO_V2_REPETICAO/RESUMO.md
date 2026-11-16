# Comparação da validação sem LLM

| Cenário | Repetições | Mediana | Intervalo |
|---|---:|---:|---:|
| OPT_FRIO_K1 | 3 | 1348.652 s | 1344.491–1356.852 s |
| OPT_FRIO_K2 | 3 | 1133.274 s | 1130.759–1206.575 s |
| OPT_QUENTE_K1 | 1 | 1068.796 s | 1068.796–1068.796 s |
| OPT_QUENTE_K2 | 1 | 1104.275 s | 1104.275–1104.275 s |
| REF_K1 | 3 | 1354.655 s | 1353.070–1364.499 s |
| SELETIVA_K1 | 1 | 1187.975 s | 1187.975–1187.975 s |

Divergências de resultados/evidências: 1.

Replays não são novas correções ou réplicas independentes de LLM.
Cache quente mede reutilização, não nova medição de qualidade.
Resultados de oito patches não garantem cobertura dos 78 casos.
Pico de RSS amostrado soma páginas potencialmente compartilhadas.
