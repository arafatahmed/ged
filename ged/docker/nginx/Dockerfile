# Image du frontal : compile l'application Angular puis la sert avec Nginx,
# qui fait aussi office de reverse proxy vers Django (API, administration technique).
# Contexte de construction : le dossier ged/ (voir compose.yaml).

FROM node:22.20-bookworm-slim AS construction
WORKDIR /frontend
ENV NG_CLI_ANALYTICS=false CI=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx ng build --configuration production

FROM nginx:1.28-alpine
COPY --from=construction /frontend/dist/frontend/browser /srv/frontend
COPY docker/nginx/ged.conf /etc/nginx/conf.d/default.conf
COPY docker/nginx/snippets /etc/nginx/snippets
