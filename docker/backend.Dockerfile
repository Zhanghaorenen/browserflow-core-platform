FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/opt/browsers ANONYMIZED_TELEMETRY=false
RUN apt-get update && apt-get install -y --no-install-recommends gcc pkg-config default-libmysqlclient-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install --no-cache-dir uv==0.13.7 && uv sync --frozen --extra agent --extra mysql --no-install-project
ENV PATH="/app/backend/.venv/bin:$PATH"
RUN python -m playwright install --with-deps chromium && chmod -R a+rX /opt/browsers
COPY backend/ ./
COPY demo-sites /app/demo-sites
RUN useradd -m -u 10001 app && mkdir -p media staticfiles && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["daphne","-b","0.0.0.0","-p","8000","config.asgi:application"]
