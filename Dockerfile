# Multi-stage Dockerfile for AtomSpace Builder API
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

ARG API_PORT

# Install system dependencies (including Java for HugeGraph Loader)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    default-jre-headless \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 1. Copy the frozen engine binary
COPY binaries/apache-hugegraph-loader-incubating-1.5.0.tar.gz /tmp/engine.tar.gz

# 2. Extract the engine
RUN mkdir -p /app/hugegraph-loader && \
    tar -xzf /tmp/engine.tar.gz -C /app/hugegraph-loader/ && \
    rm /tmp/engine.tar.gz && \
    mv /app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0 /app/hugegraph-loader/current

# 3. Inject the pre-built custom plugin JAR locally built
COPY hugegraph-loader-custom/target/hugegraph-loader-custom-1.5.0.jar /app/hugegraph-loader/current/lib/

# Copy application code
COPY app/ ./app/
COPY config.yaml .
# Note: .env is usually mounted or passed as env vars, but copying for local dev convenience
COPY .env .env

# Create directories and set permissions
RUN mkdir -p output uploads logs && \
    find /app/hugegraph-loader -name "*.sh" -exec sed -i 's/\r$//' {} + && \
    find /app/hugegraph-loader -name "*.sh" -exec chmod +x {} \;

# Environment variables with correct path
ENV PYTHONPATH=/app
ENV HUGEGRAPH_LOADER_PATH=/app/hugegraph-loader/current/bin/hugegraph-loader.sh

# Verify the HugeGraph Loader is properly installed
RUN echo "Verifying HugeGraph Loader installation..." && \
    ls -la /app/hugegraph-loader/current/bin/ && \
    echo "HugeGraph Loader path: $HUGEGRAPH_LOADER_PATH" && \
    test -f "$HUGEGRAPH_LOADER_PATH" && \
    echo "HugeGraph Loader verification successful"

# Health check
# HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:$API_PORT/api/health || exit 1

EXPOSE $API_PORT

CMD ["python", "-m", "app.main"]