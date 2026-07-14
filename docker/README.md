# docker/

Reserved for deployment-related assets that don't belong inside either
service's own image: reverse-proxy config (e.g. nginx for serving the built
frontend), production `docker-compose.override.yml` files, and eventually
orchestration manifests.

Nothing lives here yet — `backend/Dockerfile`, `frontend/Dockerfile`, and
the root `docker-compose.yml` are enough to run both services locally.
This directory is scaffolding for when actual deployment is implemented.
