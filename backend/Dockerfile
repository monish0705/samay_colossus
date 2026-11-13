FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY backend/requirements-lock.txt backend/requirements-lock.txt
RUN pip install --no-cache-dir -r backend/requirements-lock.txt
COPY backend backend
COPY scripts scripts
RUN pip install --no-cache-dir --no-deps ./backend && useradd --create-home samay && mkdir -p /app/runtime && chown samay /app/runtime
USER samay
ENV SAMAY_DATABASE_URL=sqlite:////app/runtime/samay.db SAMAY_ENVIRONMENT=production
EXPOSE 8000
CMD ["python", "scripts/container_start.py"]
