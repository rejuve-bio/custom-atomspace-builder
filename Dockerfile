FROM maven:3.8-openjdk-17 AS hugegraph-builder

WORKDIR /build

COPY pom.xml .
COPY hugegraph-loader/pom.xml hugegraph-loader/
COPY hugegraph-client/pom.xml hugegraph-client/
COPY hugegraph-loader-custom/pom.xml hugegraph-loader-custom/
RUN mvn dependency:go-offline -pl hugegraph-client,hugegraph-loader,hugegraph-loader-custom -am

COPY . .
RUN if [ -d "hugegraph-loader" ] && [ -f "hugegraph-loader/pom.xml" ]; then \
        echo "Building HugeGraph Loader from source..."; \
        mvn clean install -pl hugegraph-client,hugegraph-loader,hugegraph-loader-custom -am \
            -Dmaven.javadoc.skip=true \
            -DskipTests \
            -Dcheckstyle.skip=true \
            -Deditorconfig.skip=true && \
        echo "HugeGraph Loader built successfully"; \
        ls -la hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/; \
    else \
        echo "ERROR: hugegraph-loader source not found!"; \
        echo "Available directories:"; ls -la; \
        exit 1; \
    fi

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HUGEGRAPH_LOADER_PATH=/app/hugegraph-loader/bin/hugegraph-loader.sh

ARG API_PORT=8000
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    default-jre-headless \
    bash \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=hugegraph-builder /build/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0 /app/hugegraph-loader

COPY app/ ./app/
COPY config.yaml .

RUN mkdir -p output uploads logs \
    && chmod +x /app/hugegraph-loader/bin/hugegraph-loader.sh

RUN echo "Verifying HugeGraph Loader installation..." && \
    ls -la /app/hugegraph-loader/bin/ && \
    echo "HugeGraph Loader path: $HUGEGRAPH_LOADER_PATH" && \
    test -f "$HUGEGRAPH_LOADER_PATH" && \
    echo "HugeGraph Loader verification successful"

EXPOSE ${API_PORT}
CMD ["python", "-m", "app.main"]
