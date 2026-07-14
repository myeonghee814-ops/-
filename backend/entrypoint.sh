#!/usr/bin/env bash
# Production entrypoint: apply any pending migrations, then start the
# server. Fine for a single-instance/small-scale deployment; if this ever
# scales to multiple replicas deploying simultaneously, move the `alembic
# upgrade head` step to a separate one-off job that runs before the new
# replicas start, so they don't race to migrate concurrently.
set -euo pipefail

echo "Applying database migrations..."
alembic upgrade head

echo "Starting application..."
exec "$@"
