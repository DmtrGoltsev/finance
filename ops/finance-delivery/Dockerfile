FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/finance
COPY apps/backend/pyproject.toml apps/backend/README.md ./apps/backend/
COPY apps/backend/src ./apps/backend/src
RUN pip install --no-cache-dir ./apps/backend && useradd --uid 10001 --no-create-home finance
USER 10001
CMD ["python", "-m", "app.delivery.worker"]
