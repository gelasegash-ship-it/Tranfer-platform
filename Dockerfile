# ============================================================================
# TRANSFER PLATFORM - DOCKERFILE
# Build: docker build -t transfer-api:latest .
# Run: docker run -p 8000:8000 transfer-api:latest
# ============================================================================

# Stage 1: Build
FROM python:3.10-slim as builder

WORKDIR /tmp

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Build wheels
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy app code
COPY transfer-backend-sqlite.py .
COPY transfer-api-fastapi.py .
COPY .env.example .env

# Create data directory
RUN mkdir -p /app/data /app/logs

# Set environment
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run app
CMD ["python", "transfer-api-fastapi.py"]

# Expose port
EXPOSE 8000

# Metadata
LABEL maintainer="Gelase <gelase@transfer.app>"
LABEL description="TRANSFER Platform - African Fintech API"
LABEL version="3.0.0"
