# Usage: make new NAME=my-project [DEST=..] [YES=1]
#
# Copies this template into $(DEST)/$(NAME), without the template's .git.
# The target may be absent or an empty directory (e.g. made by root with `install -d`).
# It shows the target path and asks for confirmation first (Enter = yes).
# It does not touch git in the new project. Run git init yourself (see README).

SHELL := /bin/bash

# Ignore NAME from the environment (often set to the hostname); accept it only on the command line.
ifneq ($(origin NAME),command line)
NAME :=
endif

DEST   ?= ..
SRC    := $(CURDIR)
TARGET := $(abspath $(DEST)/$(NAME))

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@printf 'Usage: make <target> [VAR=value]\n\n'
	@printf 'Targets:\n'
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
	  | sed -E 's/^([a-zA-Z_-]+):.*## (.*)/  \1\t\2/'
	@printf '\nVariables (for "new"):\n'
	@printf '  NAME\tProject directory name (required)\n'
	@printf '  DEST\tParent directory (default: ..)\n'
	@printf '  YES\tSet to 1 to skip the confirmation prompt\n'
	@printf '\nVariables (for "rag-*"):\n'
	@printf '  GPU\t1 (or true/yes) lets the ollama container use the NVIDIA GPU (rag-up)\n'
	@printf '  PROJECT\tProject name stored in the DB (rag-ingest; default: this directory name)\n'
	@printf '  DOCS\tDirectory of Markdown to ingest (rag-ingest; default: docs)\n'
	@printf '  Q\tQuestion (rag-search)\n'
	@printf '\nExample:\n  make new NAME=my-project\n'

.PHONY: new
.SILENT: new
new: ## Copy this template into DEST/NAME (without .git)
	@test -n "$(NAME)" || { echo "Error: NAME is required. Usage: make new NAME=my-project"; exit 1; }
	@if [ -e "$(TARGET)" ]; then \
	  { [ -d "$(TARGET)" ] && [ -z "$$(ls -A "$(TARGET)")" ]; } \
	    || { echo "Error: $(TARGET) already exists and is not an empty directory."; exit 1; }; \
	fi
	@echo "Project will be created at: $(TARGET)"
	@if [ -z "$(YES)" ]; then \
	  read -r -p "Create it? [Y/n] " ans; \
	  case "$$ans" in ""|[Yy]|[Yy][Ee][Ss]) ;; *) echo "Aborted."; exit 1;; esac; \
	fi
	mkdir -p "$(TARGET)"
	cp -r "$(SRC)/." "$(TARGET)/"
	rm -rf "$(TARGET)/.git" "$(TARGET)/.claude/settings.local.json"
	sed -i "s/^commit:.*/commit: $$(git rev-parse --short HEAD)/; \
	        s/^date:.*/date: $$(date +%F)/" \
	  "$(TARGET)/.claude/TEMPLATE_VERSION"
	test -e "$(TARGET)/docs/brainstorming-intake.md" \
	  || cp "$(TARGET)/docs/templates/brainstorming-intake.md" "$(TARGET)/docs/brainstorming-intake.md"
	@echo "Created: $(TARGET)"
	@echo "Next: cd $(TARGET), then set up git (see README)."

# ---- RAG (design: docs/design/rag-minimal-pipeline.md) ----
RAG_DIR     := rag
RAG_MODEL   ?= bge-m3
RAG_GPU     := $(filter 1 true yes,$(GPU))
RAG_COMPOSE := docker compose -f $(RAG_DIR)/compose.yaml$(if $(RAG_GPU), -f $(RAG_DIR)/compose.gpu.yaml)
RAG_PY      := $(RAG_DIR)/.venv/bin/python
DOCS        ?= docs
K           ?= 5
QFILE       ?= docs/rag/eval-questions.md
RAG_PROJECT := $(if $(filter command line,$(origin PROJECT)),$(PROJECT),$(notdir $(CURDIR)))
RAG_ONLY    := $(if $(filter command line,$(origin PROJECT)),--project "$(PROJECT)")

.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest rag-search rag-eval rag-test

rag-up: ## Start the RAG containers (db, ollama) and pull the model (GPU=1: use the NVIDIA GPU)
	@$(RAG_COMPOSE) up -d --build --wait
	@if $(RAG_COMPOSE) exec -T ollama ollama list | grep -q '^$(RAG_MODEL)'; then \
	  echo "model $(RAG_MODEL): already present"; \
	else \
	  echo "pulling $(RAG_MODEL) (first time only; about 1.2GB download)"; \
	  $(RAG_COMPOSE) exec -T ollama ollama pull $(RAG_MODEL); \
	fi
	@echo "RAG is up. db: 127.0.0.1:5432  ollama: 127.0.0.1:11434  mcp: http://127.0.0.1:8000/mcp"

rag-down: ## Stop the RAG containers (data is kept)
	@$(RAG_COMPOSE) down

rag-destroy: ## Stop the RAG containers and DELETE their data (db, models)
	@if [ -z "$(YES)" ]; then \
	  read -r -p "Delete the RAG containers and ALL their data (db, models)? [y/N] " ans; \
	  case "$$ans" in [Yy]|[Yy][Ee][Ss]) ;; *) echo "Aborted."; exit 1;; esac; \
	fi
	@$(RAG_COMPOSE) down -v

# The venv is tied to its location. A venv copied by `make new` carries the old location in its marker,
# so it is rebuilt here (every new project builds its own venv).
rag-venv:
	@if [ ! -f $(RAG_DIR)/.venv/.ready ] \
	  || [ "$$(cat $(RAG_DIR)/.venv/.ready)" != "$(abspath $(RAG_DIR))" ] \
	  || [ $(RAG_DIR)/requirements.txt -nt $(RAG_DIR)/.venv/.ready ]; then \
	  echo "setting up $(RAG_DIR)/.venv (python venv + psycopg)"; \
	  rm -rf $(RAG_DIR)/.venv; \
	  python3 -m venv $(RAG_DIR)/.venv && \
	  $(RAG_DIR)/.venv/bin/pip install -q -r $(RAG_DIR)/requirements.txt && \
	  echo "$(abspath $(RAG_DIR))" > $(RAG_DIR)/.venv/.ready; \
	fi

rag-ingest: rag-venv ## Ingest Markdown into the DB (PROJECT=name DOCS=dir)
	@$(RAG_PY) $(RAG_DIR)/ingest.py --docs "$(DOCS)" --project "$(RAG_PROJECT)" $(foreach e,$(EXCLUDE),--exclude "$(e)")

rag-search: rag-venv ## Search the DB (Q="question" [K=5] [PROJECT=name] [TYPE=adr|design|plan|shared|other])
	@test -n "$$Q" || { echo 'Error: Q is required. Usage: make rag-search Q="question"'; exit 1; }
	@$(RAG_PY) $(RAG_DIR)/search.py "$$Q" --k "$(K)" $(RAG_ONLY) $(if $(TYPE),--doc-type "$(TYPE)")

.PHONY: rag-status
rag-status: ## Show what is in the DB (files and chunks per project and type)
	@$(RAG_COMPOSE) exec -T db psql -U rag -d rag \
	  -c "SELECT metadata->>'project' AS project, metadata->>'doc_type' AS doc_type, count(DISTINCT metadata->>'path') AS files, count(*) AS chunks, max(metadata->>'commit') AS commit, max(metadata->>'model') AS model FROM knowledge GROUP BY 1, 2 ORDER BY 1, 2" \
	  -c "SELECT count(*) AS total_chunks FROM knowledge"

.PHONY: rag-mcp-check
rag-mcp-check: ## Check the MCP server end to end (initialize, tools/list, a search call)
	@python3 $(RAG_DIR)/mcp_check.py

rag-eval: rag-venv ## Run the evaluation questions against the DB (QFILE=path K=5 [PROJECT=name])
	@$(RAG_PY) $(RAG_DIR)/eval.py "$(QFILE)" --k "$(K)" $(RAG_ONLY)

rag-test: rag-venv ## Run the unit tests of rag/ (DB tests are skipped if the DB is down)
	@$(RAG_PY) -m unittest discover -s $(RAG_DIR)/tests -t $(RAG_DIR) -v
