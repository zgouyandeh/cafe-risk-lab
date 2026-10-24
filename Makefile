.PHONY: install calibrate backtest test run build-ui
PY ?= python

install:
	$(PY) -m pip install -e packages/argan_engine -e apps/api pytest httpx

calibrate:
	$(PY) -c "from argan_engine.calibrate import get_calibration; get_calibration(refresh=True)"

backtest:
	$(PY) scripts/run_backtests.py

test:
	$(PY) -m pytest -q

run:
	$(PY) -m uvicorn argan_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000

build-ui:
	cd apps/web-react && npm install && npm run build
