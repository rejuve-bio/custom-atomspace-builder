# Variables
COMPOSE_FILE=docker-compose.yml
COMPOSE_FILE_DEV=docker-compose.dev.yml
SERVICE=atomspace-api
SERVICE_DEV=atomspace-api-dev


# Default target
.DEFAULT_GOAL := help

# Show help
help:
	@echo ""
	@echo "Available commands:"
	@echo "  make build       - Build all services using docker compose"
	@echo "  make build-dev   - Build all services using docker compose in development mode"
	@echo "  make build-nc    - Build all services without using cache"
	@echo "  make build-nc-dev - Build all services without using cache in development mode"
	@echo "  make up          - Build (if needed) and start all services in detached mode"
	@echo "  make up-dev	  - Build and start all services in development mode"
	@echo "  make up-api      - Build and start only $(SERVICE) without restarting dependencies"
	@echo "  make up-api-dev  - Build and start only $(SERVICE_DEV) in development mode without restarting dependencies"
	@echo "  make down        - Stop all running containers"
	@echo "  make down-dev    - Stop all running containers in development mode"
	@echo "  make logs        - View logs for $(SERVICE)"
	@echo "  make logs-dev    - View logs for $(SERVICE_DEV) in development mode"
	@echo "  make rebuild     - Force rebuild all services and restart"
	@echo "  make rebuild-dev - Force rebuild all services in development mode and restart"
	@echo "  make clean       - Stop all containers and remove volumes (WARNING: deletes DB data)"
	@echo "  make clean-dev   - Stop all containers and remove volumes in development mode"
	@echo "  make help        - Show this help message"
	@echo ""

# Build all services (with cache)
build:
	docker compose up -d --build

# Build without cache
build-nc:
	docker-compose -f $(COMPOSE_FILE) --build --no-cache

# Build and start everything
up:
	docker-compose -f $(COMPOSE_FILE) up -d

# Build & start only API (fast when only Python changes)
up-api:
	docker-compose -f $(COMPOSE_FILE) up -d --no-deps --build $(SERVICE)

# Build and start all services EXCEPT Neo4j
up-no-neo4j:
	@echo "Starting all services except Neo4j..."
	docker-compose -f $(COMPOSE_FILE) up -d --build hugegraph $(SERVICE)

# Build and start neo4j only
up-neo4j:
	@echo "Starting only Neo4j service..."
	docker-compose -f $(COMPOSE_FILE) up -d --build neo4j
	
# Stop all containers
down:
	docker-compose -f $(COMPOSE_FILE) down

# View logs for API
logs:
	docker-compose -f $(COMPOSE_FILE) logs -f $(SERVICE)

# Rebuild everything and restart
rebuild:
	docker-compose -f $(COMPOSE_FILE) up -d --build

# Clean volumes (WARNING: deletes DB data)
clean:
	docker-compose -f $(COMPOSE_FILE) down -v


# Development targets
# Build all services in development mode
build-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) up -d --build

# Build without cache in development mode
build-nc-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) up -d --build --no-cache

# Build and start everything in development mode
up-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) up -d

# Build & start only API in development mode (fast when only Python changes)
up-api-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) up -d --no-deps --build $(SERVICE_DEV)

# Stop all containers in development mode
down-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) down

# View logs for API in development mode
logs-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) logs -f $(SERVICE_DEV)

# Rebuild everything and restart in development mode
rebuild-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) up -d --build

# Clean volumes in development mode (WARNING: deletes DB data)
clean-dev:
	docker-compose -f $(COMPOSE_FILE_DEV) down -v
