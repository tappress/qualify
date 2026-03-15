.PHONY: build install dev clean

VENV        := backend/.venv
PYTHON      := $(abspath $(VENV))/bin/python
PIP         := $(abspath $(VENV))/bin/pip
PYINSTALLER := $(abspath $(VENV))/bin/pyinstaller

# ── Full local build + install ─────────────────────────────────────────────
build: $(VENV) frontend/dist
	$(PYINSTALLER) qualify.spec --noconfirm
	@echo "Binary ready at dist/qualify"

install: build
	./install.sh

# ── Dependencies ───────────────────────────────────────────────────────────
$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --quiet -e "backend[dev]" pyinstaller

frontend/dist:
	cd frontend && npm ci && npm run build

# ── Dev mode (no build needed) ─────────────────────────────────────────────
dev:
	@trap 'kill 0' EXIT; \
	cd backend && $(PYTHON) -m uvicorn qualify.main:app --port 65444 --reload & \
	cd frontend && npm run dev & \
	wait

# ── Clean ──────────────────────────────────────────────────────────────────
clean:
	rm -rf dist build frontend/dist __pycache__ backend/src/qualify/__pycache__
