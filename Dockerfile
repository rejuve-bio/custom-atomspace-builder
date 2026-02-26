FROM alpine:latest AS binary-fetcher
RUN apk add --no-cache curl tar

ARG ENGINE_URL="https://github.com/rejuve-bio/custom-atomspace-builder/releases/download/v1.0.0/apache-hugegraph-loader-incubating-1.5.0.tar.gz"
WORKDIR /downloads
RUN curl -L ${ENGINE_URL} -o engine.tar.gz

FROM maven:3.8-openjdk-17 AS custom-plugin-builder
WORKDIR /build

#1. Extract JARs for compilation and runtime
COPY --from=binary-fetcher /downloads/engine.tar.gz .
RUN mkdir -p /tmp/engine-extracted && \
    tar -xzf engine.tar.gz -C /tmp/engine-extracted/ && \
    # Find dependencies for compilation
    LOADER_JAR=$(find /tmp/engine-extracted -name "hugegraph-loader-1.5.0.jar" | head -1) && \
    CLIENT_JAR=$(find /tmp/engine-extracted -name "hugegraph-client-1.5.0.jar" | head -1) && \
    COMMON_JAR=$(find /tmp/engine-extracted -name "hugegraph-common-1.5.0.jar" | head -1) && \
    # Find the JAR for runtime
    SHADED_JAR=$(find /tmp/engine-extracted -name "*shaded*.jar" | head -1) && \
    # Install compilation dependencies
    mvn install:install-file -Dfile=$LOADER_JAR -DgroupId=org.apache.hugegraph -DartifactId=hugegraph-loader -Dversion=1.5.0 -Dpackaging=jar -B && \
    mvn install:install-file -Dfile=$CLIENT_JAR -DgroupId=org.apache.hugegraph -DartifactId=hugegraph-client -Dversion=1.5.0 -Dpackaging=jar -B && \
    mvn install:install-file -Dfile=$COMMON_JAR -DgroupId=org.apache.hugegraph -DartifactId=hugegraph-common -Dversion=1.5.0 -Dpackaging=jar -B && \
    # Prepare runtime dependency
    mv $SHADED_JAR /tmp/runtime-shaded.jar && \
    rm -rf /tmp/engine-extracted

# 2. Build the Custom Plugin
COPY hugegraph-loader-custom/pom.xml hugegraph-loader-custom/
COPY hugegraph-loader-custom/src/ hugegraph-loader-custom/src/
RUN cd hugegraph-loader-custom && \
    mvn clean package -DskipTests -B

# run time
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HUGEGRAPH_LOADER_PATH=/app/hugegraph-loader/current/bin/hugegraph-loader.sh

ARG API_PORT
EXPOSE $API_PORT

# 1. System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    default-jre-headless \
    bash \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Engine Setup
COPY --from=binary-fetcher /downloads/engine.tar.gz /tmp/engine.tar.gz
RUN mkdir -p /app/hugegraph-loader && \
    tar -xzf /tmp/engine.tar.gz -C /app/hugegraph-loader/ && \
    rm /tmp/engine.tar.gz && \
    mv /app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0 /app/hugegraph-loader/current && \
    # cleanup conflicting JARs to ensure only the JAR extracted above is used
    rm -f /app/hugegraph-loader/current/lib/hugegraph-loader-1.5.0.jar && \
    rm -f /app/hugegraph-loader/current/lib/apache-hugegraph-loader-incubating-1.5.0-shaded.jar

# 4. Inject custom writer JARs - shaded JAR and compiled plugin
COPY --from=custom-plugin-builder /tmp/runtime-shaded.jar /app/hugegraph-loader/current/lib/apache-hugegraph-loader-incubating-1.5.0-shaded.jar
COPY --from=custom-plugin-builder /build/hugegraph-loader-custom/target/hugegraph-loader-custom-1.5.0.jar /app/hugegraph-loader/current/lib/

# 5. Application Code & Config
COPY app/ ./app/
COPY config.yaml .
COPY .env .env

# 6. Final Permissions & Setup
RUN mkdir -p output uploads logs && \
    find /app/hugegraph-loader -name "*.sh" -exec sed -i 's/\r$//' {} + && \
    find /app/hugegraph-loader -name "*.sh" -exec chmod +x {} \;

CMD ["python", "-m", "app.main"]