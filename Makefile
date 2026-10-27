# Makefile.prj - Project Automation Targets for Nerd-Dock

VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
SYSDEPS_STAMP = .system-deps.stamp
DICTATION_DEPS_STAMP = .dictation-deps.stamp
DICTATION_HOME = $(HOME)/.local/share/nerd-dictation
DICTATION_BIN = $(HOME)/.local/bin/nerd-dictation
DICTATION_MODEL_NAME = vosk-model-small-en-us-0.15
DICTATION_MODEL_DIR = $(HOME)/.config/nerd-dictation/model
VENV_STAMP = $(VENV)/.setup.stamp

.PHONY: install-dictation all setup run test lint format clean help install-system-deps install

all: help

help: ## Show this help message
	@echo "Nerd-Dock Development Automation"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-system-deps: $(SYSDEPS_STAMP) ## Install Fedora system packages via dnf (requires sudo; once)

$(SYSDEPS_STAMP):
	@echo "Installing system dependencies via dnf..."
	sudo dnf install -y \
		python3-gobject \
		gtk3 \
		libayatana-appindicator-gtk3 \
		libnotify
	touch $@

install-dictation: $(DICTATION_BIN) $(DICTATION_MODEL_DIR)/am ## Install nerd-dictation, vosk, a model and ydotool (Wayland typing)

$(DICTATION_DEPS_STAMP):
	sudo dnf install -y ydotool git curl unzip pulseaudio-utils
	touch $@

$(DICTATION_BIN): | $(DICTATION_DEPS_STAMP)
	git clone https://github.com/ideasman42/nerd-dictation.git $(DICTATION_HOME) || git -C $(DICTATION_HOME) pull
	python3 -m venv $(DICTATION_HOME)/venv
	$(DICTATION_HOME)/venv/bin/pip install vosk
	mkdir -p $(dir $@)
	printf '#!/bin/sh\nexec "%s/venv/bin/python" "%s/nerd-dictation" "$$@"\n' "$(DICTATION_HOME)" "$(DICTATION_HOME)" > $@
	chmod +x $@

$(DICTATION_MODEL_DIR)/am:
	mkdir -p $(dir $(DICTATION_MODEL_DIR))
	curl -L -o $(DICTATION_MODEL_NAME).zip https://alphacephei.com/vosk/models/$(DICTATION_MODEL_NAME).zip
	unzip -q -o $(DICTATION_MODEL_NAME).zip -d $(dir $(DICTATION_MODEL_DIR))
	rm -rf $(DICTATION_MODEL_DIR)
	mv $(dir $(DICTATION_MODEL_DIR))$(DICTATION_MODEL_NAME) $(DICTATION_MODEL_DIR)
	rm -f $(DICTATION_MODEL_NAME).zip

install: $(SYSDEPS_STAMP) install-dictation ## Install Nerd-Dock to the active python environment (pipx)
	@echo "Installing Nerd-Dock to the current python environment..."
	pipx install . --system-site-packages

setup: $(VENV_STAMP) ## Create virtualenv and install dependencies

$(VENV_STAMP): pyproject.toml | $(SYSDEPS_STAMP)
	@echo "Setting up python virtual environment with system site packages..."
	python3 -m venv --system-site-packages $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]
	touch $@
	@echo "Setup complete. Virtual environment ready."

run: $(VENV_STAMP) ## Run the Nerd-Dock tray application
	@echo "Starting Nerd-Dock..."
	PYTHONPATH=. $(PYTHON) nerd_dock/main.py

test: $(VENV_STAMP) ## Run unit tests with pytest
	@echo "Running unit tests..."
	PYTHONPATH=. $(PYTHON) -m pytest tests/ --cov=nerd_dock --cov-report=term-missing

lint: $(VENV_STAMP) ## Run comprehensive static analysis (ruff, radon, vulture, bandit, pylint)
	@echo "=== Running Ruff Linter ==="
	$(PYTHON) -m ruff check nerd_dock tests
	@echo "=== Running Ruff Formatter (Check) ==="
	$(PYTHON) -m ruff format --check nerd_dock tests
	@echo "=== Running Radon (Complexity Gate) ==="
	$(PYTHON) -m radon cc -s -nb nerd_dock
	@echo "=== Running Vulture (Dead Code Detection) ==="
	$(PYTHON) -m vulture nerd_dock
	@echo "=== Running Bandit (Security Vulnerabilities) ==="
	$(PYTHON) -m bandit -r nerd_dock
	@echo "=== Running Pylint (Duplicate Code Check) ==="
	$(PYTHON) -m pylint --disable=all --enable=duplicate-code nerd_dock
	@echo "=== Static Analysis Completed Successfully ==="

format: $(VENV_STAMP) ## Automatically format all code using Ruff
	$(PYTHON) -m ruff format nerd_dock tests
	$(PYTHON) -m ruff check --fix nerd_dock tests

clean: ## Clean up build artifacts and caches
	rm -rf .pytest_cache .coverage htmlcov .ruff_cache build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
