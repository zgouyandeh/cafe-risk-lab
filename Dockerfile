# Live version (real simulations). Build:  docker build -t argan-risk-lab .   Run:  docker run -p 8000:8000 argan-risk-lab
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
RUN pip install -e packages/argan_engine -e apps/api
# warm the calibration cache at build time so the first request is fast
RUN python -c "from argan_engine.calibrate import get_calibration; get_calibration()"
EXPOSE 8000
CMD ["sh", "-c", "uvicorn argan_api.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000}"]
