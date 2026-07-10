ARG PYTHON_BASE_IMAGE=python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api \
    HOME=/home/study-anything

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api ./apps/api

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e '.[full]'

COPY plugins ./plugins
COPY scripts/mock_http_agent.py ./scripts/mock_http_agent.py

RUN groupadd --gid 10001 study-anything \
    && useradd --uid 10001 --gid 10001 --create-home \
      --home-dir /home/study-anything --shell /usr/sbin/nologin study-anything \
    && mkdir -p /data/study-anything \
    && chown -R 10001:10001 /data/study-anything /home/study-anything

EXPOSE 8000

USER 10001:10001

CMD ["uvicorn", "study_anything.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
