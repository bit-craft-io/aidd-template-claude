# Usage: make new NAME=my-project [DEST=..] [YES=1]
#
# Copies this template into $(DEST)/$(NAME), without the template's .git.
# The target may be absent or an empty directory (e.g. made by root with `install -d`).
# It shows the target path and asks for confirmation first (Enter = yes).
# It does not touch git in the new project. Run git init yourself (see README).

# help に出す、変数と例の説明(`make help` が読む)
#@vars new
#@var NAME Project directory name (required)
#@var DEST Parent directory (default: ..)
#@var YES Set to 1 to skip the confirmation prompt
#@example make new NAME=my-project

# Ignore NAME from the environment (often set to the hostname); accept it only on the command line.
ifneq ($(origin NAME),command line)
NAME :=
endif

DEST   ?= ..
SRC    := $(CURDIR)
TARGET := $(abspath $(DEST)/$(NAME))

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
