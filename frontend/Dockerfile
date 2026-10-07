FROM node:22-alpine AS build

WORKDIR /src

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY frontend/vite.config.ts frontend/postcss.config.mjs frontend/index.html ./
COPY frontend/src ./src
COPY frontend/public ./public

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_USE_MOCK=false
# Keycloak (realm SCORING / RCC, client scoring-wb) — fixé au build par Vite.
ARG VITE_KEYCLOAK_URL=https://keycloak.app-dev.wafabail.ma
ARG VITE_KEYCLOAK_REALM=scoring-rcc
ARG VITE_KEYCLOAK_CLIENT_ID=scoring-wb
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_USE_MOCK=$VITE_USE_MOCK \
    VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL \
    VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM \
    VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache wget \
    && rm -f /etc/nginx/conf.d/default.conf

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
