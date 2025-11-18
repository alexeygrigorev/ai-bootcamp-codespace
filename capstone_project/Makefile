.PHONY: help install setup check-elasticsearch index-ground-truth index-companies run-stress-tests run-unit-tests run-judge-tests run-judge-eval process-logs dashboard export-ground-truth verify clean test

# Default target
help:
	@echo "SEC Cybersecurity Agent - Makefile Commands"
	@echo "==========================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install              - Install Python dependencies"
	@echo "  make setup                - Complete setup (install + elasticsearch + verify)"
	@echo "  make check-elasticsearch  - Check if Elasticsearch is running"
	@echo ""
	@echo "Data Indexing:"
	@echo "  make index-ground-truth  - Index ground truth filings"
	@echo "  make index-companies     - Index cybersecurity company filings"
	@echo ""
	@echo "Running:"
	@echo "  make run-stress-tests    - Run stress test suite"
	@echo "  make run-unit-tests      - Run unit tests"
	@echo "  make run-judge-tests     - Run judge evaluation tests"
	@echo "  make run-judge-eval      - Run judge evaluation on stress test results"
	@echo "  make test                - Run all tests (unit + judge)"
	@echo ""
	@echo "Monitoring:"
	@echo "  make process-logs        - Process logs into database"
	@echo "  make dashboard           - Start monitoring dashboard"
	@echo "  make export-ground-truth - Export ground truth dataset to CSV"
	@echo ""
	@echo "Utilities:"
	@echo "  make verify              - Verify installation"
	@echo "  make clean               - Clean up temporary files"
	@echo ""

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	poetry install
	@echo "✅ Dependencies installed"

# Setup Elasticsearch
setup-elasticsearch:
	@echo "Setting up Elasticsearch..."
	./src/setup_elasticsearch.sh
	@echo "✅ Elasticsearch setup complete"

# Complete setup
setup: install setup-elasticsearch verify
	@echo "✅ Complete setup finished"

# Check Elasticsearch connection
check-elasticsearch:
	@echo "Checking Elasticsearch connection..."
	poetry run python src/check_elasticsearch.py

# Index ground truth filings
index-ground-truth:
	@echo "Indexing ground truth filings..."
	poetry run python data/check_and_index_ground_truth.py
	@echo "✅ Ground truth indexing complete"

# Index cybersecurity companies
index-companies:
	@echo "Indexing cybersecurity company filings..."
	poetry run python data/index_cybersecurity_companies.py
	@echo "✅ Company indexing complete"

# Run stress tests
run-stress-tests:
	@echo "Running stress tests..."
	poetry run python src/run_stress_tests.py
	@echo "✅ Stress tests complete"

# Run unit tests
run-unit-tests:
	@echo "Running unit tests..."
	poetry run pytest eval/tests/agent_tests/ -v
	@echo "✅ Unit tests complete"

# Run judge tests
run-judge-tests:
	@echo "Running judge evaluation tests..."
	poetry run pytest eval/tests/test_judge_evaluation.py -v
	@echo "✅ Judge tests complete"

# Run judge evaluation
run-judge-eval:
	@echo "Running judge evaluation on stress test results..."
	poetry run python eval/judge_evaluator.py
	@echo "✅ Judge evaluation complete"

# Run all tests
test: run-unit-tests run-judge-tests
	@echo "✅ All tests complete"

# Process logs
process-logs:
	@echo "Processing logs..."
	poetry run python -m monitoring.runner
	@echo "✅ Log processing complete"

# Process logs in watch mode
watch-logs:
	@echo "Watching logs directory (press Ctrl+C to stop)..."
	poetry run python -m monitoring.runner --watch

# Start monitoring dashboard
dashboard:
	@echo "Starting monitoring dashboard..."
	@echo "Dashboard will be available at http://localhost:8501"
	poetry run streamlit run monitoring/app.py

# Export ground truth dataset
export-ground-truth:
	@echo "Exporting ground truth dataset..."
	poetry run python monitoring/export_ground_truth.py
	@echo "✅ Ground truth export complete"

# Verify installation
verify:
	@echo "Verifying installation..."
	@poetry run python -c "from src.sec_search_tools import search_sec_filings; from elasticsearch import Elasticsearch; es = Elasticsearch('http://localhost:9200'); print('✅ Elasticsearch connection:', 'OK' if es.ping() else 'FAILED'); print('✅ Imports successful')"
	@echo "✅ Verification complete"

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	@find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Quick start - full setup and test
quickstart: setup index-ground-truth run-stress-tests
	@echo "✅ Quick start complete!"

