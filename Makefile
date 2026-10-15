# Usage: make new NAME=my-project [DEST=..] [YES=1]
#
# Copies this template into $(DEST)/$(NAME), without the template's .git.
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
	@printf '\nExample:\n  make new NAME=my-project\n'

.PHONY: new
new: ## Copy this template into DEST/NAME (without .git)
	@test -n "$(NAME)" || { echo "Error: NAME is required. Usage: make new NAME=my-project"; exit 1; }
	@test ! -e "$(TARGET)" || { echo "Error: $(TARGET) already exists."; exit 1; }
	@echo "Project will be created at: $(TARGET)"
	@if [ -z "$(YES)" ]; then \
	  read -r -p "Continue? [Y/n] " ans; \
	  case "$$ans" in ""|[Yy]|[Yy][Ee][Ss]) ;; *) echo "Aborted."; exit 1;; esac; \
	fi
	cp -r "$(SRC)" "$(TARGET)"
	rm -rf "$(TARGET)/.git" "$(TARGET)/.claude/settings.local.json"
	sed -i "s/^commit:.*/commit: $$(git rev-parse --short HEAD)/; \
	        s/^date:.*/date: $$(date +%F)/" \
	  "$(TARGET)/.claude/TEMPLATE_VERSION"
	test -e "$(TARGET)/docs/brainstorming-intake.md" \
	  || cp "$(TARGET)/docs/templates/brainstorming-intake.md" "$(TARGET)/docs/brainstorming-intake.md"
	@echo "Created: $(TARGET)"
	@echo "Next: cd $(TARGET), then set up git (see README)."
