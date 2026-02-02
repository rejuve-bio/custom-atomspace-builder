FROM maven:3.8-openjdk-17 AS builder

WORKDIR /build

# Cache dependencies
COPY pom.xml .
COPY hugegraph-loader/pom.xml hugegraph-loader/
COPY hugegraph-client/pom.xml hugegraph-client/
COPY hugegraph-loader-custom/pom.xml hugegraph-loader-custom/
RUN mvn dependency:go-offline -pl hugegraph-client,hugegraph-loader,hugegraph-loader-custom -am

# Build
COPY . .
RUN mvn clean install -pl hugegraph-client,hugegraph-loader,hugegraph-loader-custom -am \
    -Dmaven.javadoc.skip=true \
    -DskipTests \
    -Dcheckstyle.skip=true \
    -Deditorconfig.skip=true

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HUGEGRAPH_LOADER_PATH=/app/hugegraph-loader/bin/hugegraph-loader.sh

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    default-jre-headless \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Import built artifacts from builder stage
COPY --from=builder /build/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0 /app/hugegraph-loader

COPY app/ ./app/
COPY config.yaml .
COPY verify_atomspace.py .

RUN mkdir -p output uploads logs \
    && chmod +x /app/hugegraph-loader/bin/hugegraph-loader.sh

# Sanity check for loader binary
RUN if [ ! -f "$HUGEGRAPH_LOADER_PATH" ]; then \
        echo "Error: HugeGraph Loader binary missing at $HUGEGRAPH_LOADER_PATH"; \
        exit 1; \
    fi

EXPOSE 8000

CMD ["python", "-m", "app.main"]
