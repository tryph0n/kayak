.PHONY: help setup test test-integration lint run weather scrape-hotels setup-scraping merge-data etl verify-db visualize dashboard clean all

UV := uv

help:
	@echo "Kayak Travel Recommender - Available commands:"
	@echo ""
	@echo "  make all              Run complete pipeline: weather → scrape → merge → etl → dashboard"
	@echo "  make setup            Setup project (installs all dependencies)"
	@echo "  make setup-scraping   Install Playwright browsers (required once before scraping)"
	@echo "  make test             Run unit tests"
	@echo "  make test-integration Run integration tests (real API calls)"
	@echo "  make lint             Run flake8 linter"
	@echo "  make weather          Run weather pipeline and generate Top-5 destinations"
	@echo "  make scrape-hotels    Scrape hotels from Top-5 destinations (requires 'make weather' first)"
	@echo "  make merge-data       Merge weather + hotels data and generate Top-20 final recommendations"
	@echo "  make etl              Run ETL pipeline: S3 → PostgreSQL NeonDB (requires 'make merge-data' first)"
	@echo "  make verify-db        Verify database integrity after ETL (requires 'make etl' first)"
	@echo "  make visualize        Generate Plotly visualizations (requires 'make etl' first)"
	@echo "  make dashboard        Start Streamlit dashboard (requires 'make etl' first)"
	@echo "  make clean            Clean temporary files"
	@echo ""
	@echo "For direct uv usage, see README.md"

setup:
	@echo "Syncing dependencies with uv..."
	$(UV) sync --extra dev --extra scraping
	@if [ ! -f .env ]; then \
		echo "Creating .env from template..."; \
		cp .env.template .env; \
		echo "Please edit .env with your API keys"; \
	fi
	@mkdir -p data/output
	@echo "Setup complete! See README.md for uv usage."

setup-scraping:
	@echo "Installing playwright browsers..."
	$(UV) run playwright install chromium
	@echo "✓ Scraping environment ready"

test:
	@echo "Running unit tests..."
	$(UV) run pytest tests/ -v --tb=short -m "not integration"

test-integration:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		exit 1; \
	fi
	@echo "Running integration tests (real API calls)..."
	@set -a && . ./.env && set +a && \
	RUN_INTEGRATION_TESTS=1 \
	$(UV) run pytest tests/ -v -s -m "integration"

lint:
	@echo "Running flake8..."
	$(UV) run flake8 src/ tests/

weather:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Running weather pipeline..."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run python src/api/orchestration.py

scrape-hotels:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Scraping hotels from Top-5 destinations..."
	@echo "Note: This requires 'make weather' to have been run first."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run python -m src.apps.scraping.run_top5

merge-data:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Merging weather and hotels data..."
	@echo "Note: This requires 'make weather' and 'make scrape-hotels' to have been run first."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run python -m src.apps.data.merger

etl:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Running ETL pipeline: S3 → PostgreSQL NeonDB..."
	@echo "Note: This requires 'make merge-data' to have been run first."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run python -m src.apps.database.etl

verify-db:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Verifying database integrity..."
	@echo "Note: This requires 'make etl' to have been run first."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run python -m src.apps.database.verify

visualize:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Generating Plotly visualizations..."
	@echo "Note: This requires 'make etl' to have been run first."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run python -m src.apps.visualization.generate

dashboard:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found"; \
		echo "Run 'make setup' first and configure your .env"; \
		exit 1; \
	fi
	@echo "Starting Streamlit dashboard..."
	@echo "Note: This requires 'make etl' to have been run first."
	@set -a && . ./.env && set +a && \
	PYTHONPATH=. \
	$(UV) run streamlit run src/dashboard.py

all:
	@echo "Running complete pipeline..."
	@echo ""
	@$(MAKE) weather
	@echo ""
	@$(MAKE) scrape-hotels
	@echo ""
	@$(MAKE) merge-data
	@echo ""
	@$(MAKE) etl
	@echo ""
	@$(MAKE) visualize
	@echo ""
	@echo "Pipeline complete! Starting dashboard..."
	@$(MAKE) dashboard

clean:
	@echo "Cleaning temporary files..."
	@rm -rf __pycache__ .pytest_cache .coverage htmlcov
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete"
