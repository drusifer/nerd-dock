# Thin forwarding shim to Taskfile.yml (go-task) for `make` and `bobp make` muscle memory.
# All tasks, dependencies, and caching live in Taskfile.yml.
# Install `task` and the project toolchain via: mise install

# Pick up mise-installed tools even if the caller's shell has not run `mise activate`.
export PATH := $(HOME)/.local/share/mise/shims:$(HOME)/.local/bin:/snap/bin:$(PATH)

TASK := $(shell command -v task 2>/dev/null || command -v go-task 2>/dev/null)

.PHONY: all help _check-task install-system-deps

all: help

# Kept here because it must work before `task` is installed. It is the only target
# that uses sudo: OS packages cannot come from mise (see docs/SDLC.md).
install-system-deps: ## Install Fedora system packages via dnf (requires sudo)
	sudo dnf install -y python3-gobject gtk3 libayatana-appindicator-gtk3 \
		libnotify pulseaudio-utils ydotool git curl unzip

help: _check-task
	@$(TASK) --list

_check-task:
	@if [ -z "$(TASK)" ]; then \
		echo "Error: 'task' (go-task) is not installed."; \
		echo "Install the toolchain with 'mise install' (https://mise.jdx.dev) or install Task directly (https://taskfile.dev/installation/)."; \
		exit 1; \
	fi

# Prevent the catch-all rule from matching build files themselves.
Makefile Taskfile.yml mise.toml: ;

%: _check-task
	@$(TASK) $@ $(if $(ARGS),-- $(ARGS))
