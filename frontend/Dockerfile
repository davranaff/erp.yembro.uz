FROM node:22-alpine AS base

# ── deps ──────────────────────────────────────────────────────────────────────
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ── builder ───────────────────────────────────────────────────────────────────
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time public env vars (baked into the browser bundle).
# Exposed as ARG → ENV so `next build` picks them up.
ARG NEXT_PUBLIC_API_URL=/api
ARG NEXT_PUBLIC_AUTH_LOGIN_ENDPOINT=/api/auth/token/
ARG NEXT_PUBLIC_REQUEST_TIMEOUT_MS=15000
ARG NEXT_PUBLIC_APP_NAME=Yembro

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_AUTH_LOGIN_ENDPOINT=$NEXT_PUBLIC_AUTH_LOGIN_ENDPOINT \
    NEXT_PUBLIC_REQUEST_TIMEOUT_MS=$NEXT_PUBLIC_REQUEST_TIMEOUT_MS \
    NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME \
    NEXT_TELEMETRY_DISABLED=1

# Use `npx next build` directly to bypass the NODE_OPTIONS=--no-webstorage
# flag baked into package.json scripts (that flag is for Chromium wrappers,
# Node doesn't accept it and crashes).
RUN npx next build

# ── runner ────────────────────────────────────────────────────────────────────
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 \
    HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
