ARG PYTHON_BASE_IMAGE=python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api ./apps/api

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

COPY plugins ./plugins
COPY scripts/mock_http_agent.py ./scripts/mock_http_agent.py

EXPOSE 8000

CMD ["uvicorn", "neural_console.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
