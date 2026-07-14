# Multi-stage: one Dockerfile, two targets, selected via `--target` in the
# relevant docker-compose file. `development` mirrors what used to be the
# whole file (hot reload, runs as root, source bind-mounted over the image
# by the dev compose file); `production` adds a non-root user, multiple
# gunicorn+uvicorn worker processes, and a migration-then-serve entrypoint.
FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ---------------------------------------------------------------------------
FROM base AS development

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
FROM base AS production

RUN addgroup --system app \
    && adduser --system --ingroup app --no-create-home app \
    && chown -R app:app /app \
    && chmod +x entrypoint.sh
USER app

EXPOSE 8000

# gunicorn reads its worker count from WEB_CONCURRENCY natively (falls back
# to 1 if unset) -- deliberately not passed as a --workers CLI flag below,
# since an explicit flag would always win over the env var and defeat the
# point of making it configurable per-deployment via docker-compose.prod.yml.
ENV WEB_CONCURRENCY=4

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
