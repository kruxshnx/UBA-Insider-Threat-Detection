# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile — UBA Backend (FastAPI + ML Models)
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

LABEL maintainer="UBA-ITD" \
      description="Backend API and ML inference for UBA Insider Threat Detection"

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY config.yaml .
COPY src/ ./src/
COPY data/ ./data/
RUN mkdir -p ./models/lstm ./models/baseline ./models/hybrid

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health'); assert r.status_code==200"

# Default: run the API server
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
