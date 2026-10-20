# Usage: make <target> [VAR=value]   (`make` alone shows the list)
#
# Commands live in make.d/*.mk, one file per topic.
# To add a topic: create make.d/<topic>.mk, then add one include line below.
#   - A target with a trailing "## description" shows up in `make help`.
#   - Variables and examples are documented in the same .mk:
#       #@vars <topic>          heading of the variable list
#       #@var NAME description  one variable
#       #@example <command>     one example

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ========================================
# include
# ----------------------------------------
include make.d/template.mk   # Copy this template into a new project (make new)

# ========================================
# command
# ----------------------------------------
.PHONY: help
help: ## Show this help
	@printf 'Usage: make <target> [VAR=value]\n\n'
	@printf 'Targets:\n'
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
	  | sed -E 's/^([a-zA-Z_-]+):.*## (.*)/  \1\t\2/'
	@awk '/^#@vars /{sub(/^#@vars /, ""); printf "\nVariables (for \"%s\"):\n", $$0; next} \
	  /^#@var /{n = $$2; t = substr($$0, index($$0, n) + length(n) + 1); printf "  %s\t%s\n", n, t}' $(MAKEFILE_LIST)
	@awk '/^#@example /{if (!h) {printf "\nExample:\n"; h = 1} sub(/^#@example /, ""); print "  " $$0}' $(MAKEFILE_LIST)
