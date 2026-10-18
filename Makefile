PYTHON ?= python3
SEMGREP ?= semgrep
K ?= 4
CONFIG ?= config/execucao.yaml

.PHONY: test-unit test-rules docker-help docker-lockfiles docker-build docker-setup \
        docker-ambiente docker-test docker-test-rules docker-shell docker-painel \
        docker-preflight docker-dry-run docker-real

test-unit:
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'

test-rules:
	$(SEMGREP) scan --test rules

# ---------------------------------------------------------------------------
# Docker: ambiente único para todos (guia em docs/docker.md)
# ---------------------------------------------------------------------------
COMPOSE ?= docker compose
RUN = $(COMPOSE) run --rm tcc

docker-help:
	@echo "Uma vez:      make docker-lockfiles  (só se docker/juice-shop/ estiver vazio)"
	@echo "Imagem:       make docker-build"
	@echo "Worktrees:    make docker-setup K=4"
	@echo "Conferir:     make docker-ambiente | make docker-test | make docker-test-rules"
	@echo "Usar:         make docker-painel | make docker-preflight | make docker-dry-run | make docker-real"
	@echo "Terminal:     make docker-shell"

docker-lockfiles:
	bash docker/gerar_lockfiles.sh

docker-build:
	$(COMPOSE) build

docker-setup:
	$(RUN) bash docker/preparar_workspace.sh $(K)

docker-ambiente:
	$(RUN) cat /opt/ambiente.json

docker-test:
	$(RUN) python -m unittest discover -s tests/unit -p 'test_*.py'

docker-test-rules:
	$(RUN) semgrep scan --test rules

docker-shell:
	$(RUN) bash

docker-painel:
	$(COMPOSE) run --rm --service-ports tcc python painel.py --endereco 0.0.0.0

docker-preflight:
	$(RUN) python executar.py --config $(CONFIG) --modo preflight

docker-dry-run:
	$(RUN) python executar.py --config $(CONFIG) --modo dry-run

docker-real:
	$(RUN) python executar.py --config $(CONFIG) --modo real
