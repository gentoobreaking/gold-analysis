# ─────────────────────────────────────────────────────────────────────────────
# Frontend Dockerfile — React / Vite static build served by nginx
# Multi-stage build: deps → builder → nginx runtime
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Dependencies ────────────────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

# Copy only package files for layer caching
COPY package.json package-lock.json* ./

# Install dependencies (frozen lockfile for reproducibility)
RUN npm ci --only=production && \
    npm ci --include=dev && true

# ── Stage 2: Build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build the production bundle
RUN npm run build

# ── Stage 3: Nginx runtime ───────────────────────────────────────────────────
FROM nginx:alpine AS runtime

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built static files
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://localhost/"]

CMD ["nginx", "-g", "daemon off;"]