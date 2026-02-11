# 1. Build stage for Custom Writer Plugin
FROM maven:3.8-openjdk-17 AS custom-plugin-builder
WORKDIR /build

# Cache dependencies separately
COPY hugegraph-loader-custom/pom.xml hugegraph-loader-custom/
COPY hugegraph-loader-custom/lib/ hugegraph-loader-custom/lib/

# Improved caching: Download dependencies AND plugins
# We run 'package' on a dummy/empty state to force Maven to download all plugins
RUN cd hugegraph-loader-custom && \
    mvn dependency:go-offline -B && \
    mvn package -DskipTests -B || true

# Now copy the source and build
COPY hugegraph-loader-custom/src/ hugegraph-loader-custom/src/
RUN cd hugegraph-loader-custom && \
    mvn clean package -DskipTests -B

# 2. Final stage
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ARG API_PORT

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    default-jre-headless \
    bash \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Binary Dependency Stage ---
# 1. Copy the frozen core engine binary
COPY binaries/apache-hugegraph-loader-incubating-1.5.0.tar.gz /tmp/engine.tar.gz

# 2. Extract the core engine
RUN mkdir -p /app/hugegraph-loader && \
    tar -xzf /tmp/engine.tar.gz -C /app/hugegraph-loader/ && \
    rm /tmp/engine.tar.gz && \
    mv /app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0 /app/hugegraph-loader/current

# 3. Inject the CUSTOM plugin JAR built in stage 1
COPY --from=custom-plugin-builder /build/hugegraph-loader-custom/target/hugegraph-loader-custom-1.5.0.jar /app/hugegraph-loader/current/lib/

# Copy application code
COPY app/ ./app/
COPY config.yaml .
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

EXPOSE $API_PORT

CMD ["python", "-m", "app.main"]