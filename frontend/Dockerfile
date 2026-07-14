# Multi-stage: `development` mirrors what used to be the whole file (Vite's
# dev server, source bind-mounted over the image by the dev compose file);
# `build` produces the static production bundle; `production` serves it via
# nginx. Selected via `--target` in the relevant docker-compose file.
FROM node:20-slim AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# ---------------------------------------------------------------------------
FROM base AS development

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]

# ---------------------------------------------------------------------------
FROM base AS build

# No VITE_API_BASE_URL/VITE_API_ROOT_URL build args needed: both default to
# relative paths (see src/services/apiClient.ts), which nginx.conf below
# proxies to the backend service, so the built bundle needs no
# environment-specific values baked in.
RUN npm run build

# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
