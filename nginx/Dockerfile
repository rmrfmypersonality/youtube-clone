FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx/proxy_params.conf /etc/nginx/proxy_params.conf
COPY --from=build /app/dist /usr/share/nginx/html