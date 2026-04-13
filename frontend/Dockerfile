FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_AUTH_LOGIN_ENDPOINT=/auth/login
ARG VITE_REQUEST_TIMEOUT_MS=15000
ARG VITE_APP_NAME=Yembro

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_AUTH_LOGIN_ENDPOINT=${VITE_AUTH_LOGIN_ENDPOINT} \
    VITE_REQUEST_TIMEOUT_MS=${VITE_REQUEST_TIMEOUT_MS} \
    VITE_APP_NAME=${VITE_APP_NAME}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
