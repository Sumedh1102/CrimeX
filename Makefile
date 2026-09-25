PY ?= .venv/bin/python
VENV ?= .venv

.PHONY: install official data preprocess train infer pipeline api web test test-ml test-api lint format web-lint web-test

install:            ## create the venv and install Python + frontend dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"
	cd frontend && npm install

official:           ## re-extract the official statement PDF and regenerate its reference doc
	$(PY) scripts/extract_official_stats.py
	$(PY) scripts/build_official_reference.py

data:               ## generate the SYNTHETIC / DEMONSTRATION incident dataset
	$(PY) scripts/generate_synthetic_data.py

preprocess:         ## data quality + gridding -> data/processed
	$(PY) scripts/preprocess_data.py

train:              ## train, calibrate and evaluate models -> artifacts/models
	$(PY) scripts/train_model.py

infer:              ## predictions for the window starting at time.as_of -> artifacts/predictions
	$(PY) scripts/run_inference.py

pipeline:           ## data -> preprocess -> train -> infer (about 4 minutes)
	$(PY) scripts/run_pipeline.py

api:                ## FastAPI on http://localhost:8000 (docs at /docs)
	$(VENV)/bin/uvicorn backend.main:app --reload --port 8000

web:                ## Next.js dashboard on http://localhost:3000
	cd frontend && npm run dev

test: test-ml test-api

test-ml:
	$(PY) -m pytest ml/tests

test-api:
	$(PY) -m pytest backend/tests

lint:
	$(VENV)/bin/ruff check ml backend scripts
	$(VENV)/bin/ruff format --check ml backend scripts

format:
	$(VENV)/bin/ruff format ml backend scripts
	$(VENV)/bin/ruff check --fix ml backend scripts

web-lint:
	cd frontend && npm run lint && npm run typecheck

web-test:
	cd frontend && npm test
