# Multi-stage Dockerfile for AtomSpace Builder API with real HugeGraph build
FROM maven:3.8-openjdk-17 AS hugegraph-builder

WORKDIR /build

# Copy the entire project (including hugegraph-loader source)
COPY . .
# Build HugeGraph Loader from source
RUN if [ -d "hugegraph-loader" ] && [ -f "hugegraph-loader/pom.xml" ]; then \
        echo "Building HugeGraph Loader from source..."; \
        mvn clean install -pl hugegraph-client,hugegraph-loader -am \
            -Dmaven.javadoc.skip=true \
            -DskipTests\
            -Dcheckstyle.skip=true \
            -Deditorconfig.skip=true && \
        echo "HugeGraph Loader built successfully"; \
        ls -la hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/; \
    else \
        echo "ERROR: hugegraph-loader source not found!"; \
        echo "Available directories:"; ls -la; \
        exit 1; \
    fi

# Python runtime stage
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

# Copy the BUILT HugeGraph Loader from builder stage
COPY --from=hugegraph-builder /build/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0 /app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0

# Copy application code
COPY app/ ./app/
COPY config.yaml .
COPY .env .env

# Create directories and set permissions
RUN mkdir -p output uploads logs && \
    find /app/hugegraph-loader -name "*.sh" -exec chmod +x {} \;

# Environment variables with correct path
ENV PYTHONPATH=/app
ENV HUGEGRAPH_LOADER_PATH=/app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/hugegraph-loader.sh

# Verify the HugeGraph Loader is properly installed
RUN echo "Verifying HugeGraph Loader installation..." && \
    ls -la /app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/ && \
    echo "HugeGraph Loader path: $HUGEGRAPH_LOADER_PATH" && \
    test -f "$HUGEGRAPH_LOADER_PATH" && \
    echo "HugeGraph Loader verification successful"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$API_PORT/api/health || exit 1

EXPOSE $API_PORT

CMD ["python", "-m", "app.main"]