# Multi-stage build for production optimization
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Install dependencies first for better caching
COPY package.json package-lock.json* ./
RUN npm ci --only=production --silent

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage with nginx
FROM nginx:alpine AS runtime

# Install curl for health checks
RUN apk add --no-cache curl

# Create non-root user
RUN addgroup -g 1001 appgroup && \
    adduser -u 1001 -G appgroup -s /bin/sh -D app

# Copy built application from builder
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set proper permissions
RUN chown -R app:appgroup /usr/share/nginx/html && \
    chown -R app:appgroup /var/cache/nginx && \
    chown -R app:appgroup /var/log/nginx && \
    chown -R app:appgroup /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R app:appgroup /var/run/nginx.pid

# Update nginx configuration to run as non-root user
RUN sed -i '/user  nginx;/c\user  app;' /etc/nginx/nginx.conf

# Switch to non-root user
USER app

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80 || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
