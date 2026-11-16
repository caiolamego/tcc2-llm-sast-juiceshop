#!/usr/bin/env bash
# Fotografa o funcionamento do projeto para comparar antes/depois da reorganização.
# Uso: bash .cache/reorganizacao/ferramentas/foto.sh antes|depois
set -uo pipefail
ROTULO="$1"
REPO=/Users/caio/Projects/tcc2-llm-sast-juiceshop
OUT="$REPO/.cache/reorganizacao/$ROTULO"
EXEC="$REPO/.cache/reorganizacao/exec"
F=.cache/reorganizacao/ferramentas
export PATH="$HOME/.docker/bin:$PATH"
RUN="docker compose run --rm -T tcc"
cd "$REPO"
[ -e "$OUT" ] && { echo "ERRO: $OUT já existe"; exit 1; }
mkdir -p "$OUT" "$EXEC"
passo(){ echo "[$(date +%H:%M:%S)] $*"; }

passo "01 identidade científica"
$RUN python $F/identidade.py > "$OUT/01_identidade.json" 2> "$OUT/01_identidade.err"; echo "exit=$?" >> "$OUT/01_identidade.err"

passo "02 inventário de arquivos (sem outputs)"
git ls-files -co --exclude-standard | grep -v '^outputs/' | while read -r f; do [ -f "$f" ] && shasum -a 256 "$f"; done | sort -k2 > "$OUT/02_arquivos.txt"
passo "02b inventário de outputs/"
git ls-files -co --exclude-standard outputs | while read -r f; do [ -f "$f" ] && shasum -a 256 "$f"; done | sort -k2 > "$OUT/02_outputs.txt"

passo "03 testes Python"
$RUN python -m unittest discover -s tests/unit -p 'test_*.py' -v > "$OUT/03_testes.txt" 2>&1; echo "exit=$?" >> "$OUT/03_testes.txt"

passo "04 testes das regras Semgrep"
$RUN semgrep scan --test rules > "$OUT/04_regras.txt" 2>&1; echo "exit=$?" >> "$OUT/04_regras.txt"

passo "05 preflight dos 52 casos (ID fixo)"
$RUN python $F/rodar_executar.py .cache/reorganizacao/config_preparados_v2.yaml preflight REORG_PREFLIGHT > "$OUT/05_preflight.log" 2>&1; echo "exit=$?" >> "$OUT/05_preflight.log"
mv "$EXEC/REORG_PREFLIGHT" "$OUT/05_preflight" 2>/dev/null; mv "$EXEC/REORG_PREFLIGHT_METRICAS" "$OUT/05_preflight_METRICAS" 2>/dev/null

passo "06 reconsolidação das métricas da campanha oficial"
$RUN python scripts/reports/consolidate_metrics.py --execucao AMP_PAINEL_20261019T183425Z_282e13b4 \
  --entrada outputs/campanha_docker/AMP_PAINEL_20261019T183425Z_282e13b4 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida .cache/reorganizacao/exec/METRICAS_OFICIAL --definicao-f criterio > "$OUT/06_metricas_oficial.log" 2>&1; echo "exit=$?" >> "$OUT/06_metricas_oficial.log"
mv "$EXEC/METRICAS_OFICIAL" "$OUT/06_metricas_oficial" 2>/dev/null
diff -r "$OUT/06_metricas_oficial" outputs/campanha_docker/AMP_PAINEL_20261019T183425Z_282e13b4_METRICAS > "$OUT/06_diff_com_arquivado.txt" 2>&1; echo "diff_exit=$?" >> "$OUT/06_diff_com_arquivado.txt"

passo "07 comandos montados pelo executar.py"
for c in config/execucao_docker_preparados.yaml config/execucao_docker_78.yaml config/execucao.yaml; do
  for m in preflight dry-run real; do echo "== $c $m"; python3 executar.py --config "$c" --modo "$m" --mostrar-comando 2>&1; done
done | sed -E 's/AMP_(PREFLIGHT|DRY_RUN|REAL)_[0-9TZ]+_[0-9a-f]{8}/AMP_\1_<ID>/g' > "$OUT/07_executar.txt"

passo "08 Makefile (make -n)"
for t in docker-help docker-build docker-setup docker-repair docker-baseline docker-check docker-ambiente docker-test docker-test-rules docker-shell docker-painel docker-preflight docker-dry-run docker-real test-unit test-rules; do
  echo "== $t"; make -n "$t" 2>&1
done > "$OUT/08_make.txt"

passo "09 painel"
docker rm -f tcc2-reorg-painel >/dev/null 2>&1
docker compose run -d --rm --service-ports --name tcc2-reorg-painel tcc python painel.py --endereco 0.0.0.0 >/dev/null 2>&1
for i in $(seq 1 60); do curl -s -o /dev/null -H 'Host: 127.0.0.1:8765' http://127.0.0.1:8765/ && break; sleep 1; done
mkdir -p "$OUT/09_painel"
for p in / /app.js /style.css /api/status /api/historico; do
  n=$(echo "$p" | tr '/' '_'); curl -s -D "$OUT/09_painel/${n}.headers" -H 'Host: 127.0.0.1:8765' "http://127.0.0.1:8765$p" > "$OUT/09_painel/${n}.body"
done
sed -i '' -E '/^(Date|date):/d' "$OUT"/09_painel/*.headers
docker stop tcc2-reorg-painel >/dev/null 2>&1

passo "10 dry-run do piloto de 10 casos (ID fixo)"
$RUN python $F/rodar_executar.py .cache/reorganizacao/config_piloto_v2.yaml dry-run REORG_DRY > "$OUT/10_dryrun.log" 2>&1; echo "exit=$?" >> "$OUT/10_dryrun.log"
mv "$EXEC/REORG_DRY" "$OUT/10_dryrun" 2>/dev/null; mv "$EXEC/REORG_DRY_METRICAS" "$OUT/10_dryrun_METRICAS" 2>/dev/null

passo "11 links da documentação"
python3 -I $F/links.py "$REPO" > "$OUT/11_links.txt" 2>&1

passo "12 referência Docker (conferência)"
python3 docker/referencia.py conferir > "$OUT/12_referencia.txt" 2>&1; echo "exit=$?" >> "$OUT/12_referencia.txt"

passo "fim"
