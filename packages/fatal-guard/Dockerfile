# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies (none for zero-dep package, but install for build)
RUN npm install --production

# Copy source files
COPY index.js register.js index.d.ts ./
COPY bin/ ./bin/
COPY src/ ./src/

# Stage 2: Runtime
FROM node:20-alpine AS runtime

# Add labels
LABEL org.opencontainers.image.source="https://github.com/Ikalus1988/MisakaNet"
LABEL org.opencontainers.image.description="fatal-guard: Zero-dependency fatal error guard"
LABEL org.opencontainers.image.licenses="MIT"

# Create non-root user
RUN addgroup -g 1001 -S fatal-guard && \
    adduser -S fatal-guard -u 1001

WORKDIR /app

# Copy from builder
COPY --from=builder /app .

# Set ownership
RUN chown -R fatal-guard:fatal-guard /app

# Switch to non-root user
USER fatal-guard

# Health check - verify the process is running
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD pgrep -f "fatal-guard.js" > /dev/null || exit 1

# Entry point
ENTRYPOINT ["node", "bin/fatal-guard.js"]
CMD ["--help"]
