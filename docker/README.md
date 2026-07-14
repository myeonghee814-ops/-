# docker/

Reserved for deployment assets that don't belong to any single service —
e.g. a shared reverse proxy sitting in front of multiple services, or
future orchestration manifests (Kubernetes, etc.).

Nothing lives here yet. The nginx config that serves the frontend's
production build lives at `frontend/nginx.conf` instead, not here: Docker
COPY paths can't reach outside a Dockerfile's own build context, and
`frontend/Dockerfile` builds with context `./frontend`, so a shared
`docker/nginx.conf` wasn't reachable from it without widening every
service's build context to the repo root. Keeping per-service config next
to the service it configures was the simpler, more conventional choice —
see docs/ARCHITECTURE.md's "Docker" section for the full reasoning.

This directory stays as scaffolding for the day something genuinely
cross-service shows up.
