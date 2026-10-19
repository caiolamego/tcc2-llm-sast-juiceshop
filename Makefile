PYTHON ?= python3
SEMGREP ?= semgrep
K ?= 4
CONFIG ?= config/execucao_docker_preparados.yaml
# Opcional: força somente o provedor do processo no container, sem editar .env.
PROVIDER ?=
LLM_ENV = $(if $(PROVIDER),-e LLM_PROVIDER=$(PROVIDER),)

.PHONY: test-unit test-rules docker-help docker-lockfiles docker-build docker-setup \
        docker-ambiente docker-test docker-test-rules docker-shell docker-painel \
        docker-preflight docker-dry-run docker-real docker-repair docker-baseline \
        docker-check docker-export docker-import

test-unit:
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'

test-rules:
	$(SEMGREP) scan --test rules

# ---------------------------------------------------------------------------
# Docker: ambiente único para todos (guia em docs/docker.md)
# ---------------------------------------------------------------------------
COMPOSE ?= docker compose
DOCKER_IMAGE = $(shell $(PYTHON) docker/referencia.py imagem)
RUN = TCC_DOCKER_IMAGE=$(DOCKER_IMAGE) $(COMPOSE) run --rm $(LLM_ENV) tcc

docker-help:
	@echo "Uma vez:      make docker-lockfiles  (só se docker/juice-shop/ estiver vazio)"
	@echo "Imagem:       make docker-build"
	@echo "Worktrees:    make docker-setup K=4"
	@echo "Reparar:      make docker-repair K=4 (preserva conteúdo divergente)"
	@echo "Mantenedor:   make docker-baseline (gera e congela uma referência, sem LLM)"
	@echo "Distribuir:   make docker-export ARQUIVO=/caminho/ambiente.tar"
	@echo "Receber:      make docker-import ARQUIVO=/caminho/ambiente.tar"
	@echo "Conferir:     make docker-ambiente | make docker-test | make docker-test-rules"
	@echo "Usar:         make docker-painel | make docker-preflight | make docker-dry-run | make docker-real"
	@echo "Terminal:     make docker-shell"

docker-lockfiles:
	bash docker/gerar_lockfiles.sh

docker-build:
	TCC_DOCKER_IMAGE=tcc2-llm-sast-juiceshop:1.0 $(COMPOSE) build

docker-setup:
	$(RUN) bash docker/preparar_workspace.sh $(K)

docker-repair:
	$(RUN) bash docker/preparar_workspace.sh $(K) --reparar-incompletos

docker-baseline:
	$(PYTHON) docker/referencia.py gerar

docker-check:
	$(PYTHON) docker/referencia.py conferir

docker-export: docker-check
	$(PYTHON) docker/referencia.py exportar --arquivo "$(ARQUIVO)"

docker-import:
	$(PYTHON) docker/referencia.py importar --arquivo "$(ARQUIVO)"

docker-ambiente:
	$(RUN) cat /opt/ambiente.json

docker-test:
	$(RUN) python -m unittest discover -s tests/unit -p 'test_*.py'

docker-test-rules:
	$(RUN) semgrep scan --test rules

docker-shell:
	$(RUN) bash

docker-painel: docker-check
	TCC_DOCKER_IMAGE=$(DOCKER_IMAGE) $(COMPOSE) run --rm --service-ports $(LLM_ENV) tcc python painel.py --endereco 0.0.0.0 --config $(CONFIG)

docker-preflight: docker-check
	$(RUN) python executar.py --config $(CONFIG) --modo preflight

docker-dry-run: docker-check
	$(RUN) python executar.py --config $(CONFIG) --modo dry-run

docker-real: docker-check
	$(RUN) python executar.py --config $(CONFIG) --modo real
