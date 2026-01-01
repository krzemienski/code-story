# Code Story Mobile - Production Dockerfile
# Builds Expo web export for static hosting

# Stage 1: Builder
FROM node:20-alpine AS builder

WORKDIR /app

# Install system dependencies for native builds
RUN apk add --no-cache git python3 make g++

# Copy package files
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./

# Install dependencies
RUN if [ -f pnpm-lock.yaml ]; then \
      npm install -g pnpm && pnpm install --frozen-lockfile; \
    elif [ -f yarn.lock ]; then \
      yarn install --frozen-lockfile; \
    elif [ -f package-lock.json ]; then \
      npm ci; \
    else \
      npm install; \
    fi

# Copy source code
COPY . .

# Build web export
RUN npx expo export --platform web

# Stage 2: Runtime with nginx
FROM nginx:alpine AS runtime

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built web assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user and set permissions
RUN addgroup -g 1001 -S nginx-user && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G nginx-user nginx-user && \
    chown -R nginx-user:nginx-user /var/cache/nginx /var/run /var/log/nginx /usr/share/nginx/html && \
    touch /var/run/nginx.pid && \
    chown -R nginx-user:nginx-user /var/run/nginx.pid

# Use non-root user
USER nginx-user

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
