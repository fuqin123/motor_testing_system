FROM node:22-alpine AS build

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --registry="${NPM_REGISTRY}"

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

ENV TZ=Asia/Shanghai

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
