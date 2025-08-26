.PHONY: install install-dev test clean lint format run help

# Variables
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

help: ## Show this help message
	@echo "EldersVR CLI - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: $(VENV)/bin/activate ## Install dependencies
$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	touch $(VENV)/bin/activate

install-dev: install ## Install development dependencies
	$(PIP) install pytest pytest-cov black flake8 mypy

test: ## Run tests
	$(PYTHON) -m pytest tests/ -v

test-coverage: ## Run tests with coverage
	$(PYTHON) -m pytest tests/ --cov=eldersvr_cli --cov-report=html --cov-report=term

lint: ## Lint code with flake8
	$(PYTHON) -m flake8 eldersvr_cli/ tests/

format: ## Format code with black
	$(PYTHON) -m black eldersvr_cli/ tests/

type-check: ## Type check with mypy
	$(PYTHON) -m mypy eldersvr_cli/

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

clean-downloads: ## Clean downloaded content
	rm -rf downloads/

run-auth: ## Authenticate with backend
	$(PYTHON) -m eldersvr_cli.cli auth

run-list: ## List connected devices
	$(PYTHON) -m eldersvr_cli.cli list-devices

run-deploy: ## Run complete deployment
	$(PYTHON) -m eldersvr_cli.cli deploy --auto

run-verify: ## Verify deployment
	$(PYTHON) -m eldersvr_cli.cli verify --deployment

run-list-dirs: ## List directories on configured devices
	$(PYTHON) -m eldersvr_cli.cli list-directories

run-compare-dirs: ## Compare directories between master and slave
	$(PYTHON) -m eldersvr_cli.cli list-directories --compare

build: ## Build distribution packages
	$(PYTHON) setup.py sdist bdist_wheel

install-package: build ## Install built package
	$(PIP) install dist/*.whl --force-reinstall

uninstall: ## Uninstall package
	$(PIP) uninstall eldersvr-cli -y

check-adb: ## Check ADB connectivity
	@echo "Checking ADB installation..."
	@adb version || echo "ADB not found in PATH"
	@echo "Connected devices:"
	@adb devices

setup-dev: install-dev ## Complete development setup
	@echo "Development environment setup complete!"
	@echo "Activate with: source $(VENV)/bin/activate"
	@echo "Run CLI with: eldersvr-onboard --help"

demo: ## Run demo sequence
	@echo "EldersVR CLI Demo"
	@echo "=================="
	$(PYTHON) -m eldersvr_cli.cli list-devices
	@echo ""
	$(PYTHON) -m eldersvr_cli.cli auth
	@echo ""
	@echo "Demo complete!"