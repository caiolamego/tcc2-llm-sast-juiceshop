#!/bin/bash
# Gera a evidência conjunta da RRIS dos três modelos, em sequência, sem LLM.
export TCC_DOCKER_IMAGE=sha256:81fe6403f07a05ccf7a911211e54ff2ae44c6b12237768b0a84ec1c7167ff5be
for E in AMP_REAL_20261106T105533Z_aa697342 AMP_REAL_20261106T125801Z_0eb68fe4 AMP_REAL_20261106T151004Z_f49ac0d2; do
  docker compose run -T --rm --no-deps tcc .venv/bin/python scripts/experimento/avaliacao_conjunta_rris.py \
    --entrada outputs/campanha_docker/$E --execucao $E --saida outputs/rris/$E \
    --baseline-testes outputs/cobertura_funcional/IMAGEM_81FE_D3_20261106/baseline/baseline_testes.json \
    > outputs/rris/$E.console.log 2>&1
  echo "codigo=$?" >> outputs/rris/$E.console.log
done
