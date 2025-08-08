# Custom Atomspace Builder API

The Custom AtomSpace Builder is a comprehensive graph processing system that transforms structured tabular data into multiple knowledge graph formats including MeTTa-formatted graphs, Neo4j-compatible formats, and MORK database integration. Built on Apache HugeGraph Loader with custom modifications, it provides a complete pipeline for data ingestion, schema transformation, and graph generation with support for multiple output formats and backend integrations.

## Overview

This project provides a flexible graph data loading and transformation pipeline with:

- RESTful API interface for data loading operations
- Multi-backend support (Neo4j, HugeGraph, and MORK) with configurable writer system
- Automatic MeTTa language representation generation for logic-based graph processing
- MORK database integration for advanced knowledge representation
- Multi-tenancy support with tenant-based graph isolation
- Comprehensive job management with history tracking
- Schema conversion and transformation utilities
- Integration with annotation services for AtomSpace interaction
- Thread-safe file operations for concurrent processing
- Direct Neo4j integration with CSV and Cypher file generation
- Makefile-based development workflow for streamlined operations

## Project Structure

```
custom-atomspace-builder/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app setup and lifespan
│   ├── config.py              # Centralized configuration management
│   │
│   ├── core/                  # Core functionality
│   │   ├── database.py        # Neo4j connection management
│   │   ├── session_manager.py # Upload session management
│   │   └── background_tasks.py # Background cleanup tasks
│   │
│   ├── models/                # Data models
│   │   ├── schemas.py         # Pydantic models
│   │   └── enums.py          # Enumerations
│   │
│   ├── services/              # Business logic
│   │   ├── hugegraph_service.py    # HugeGraph operations
│   │   ├── neo4j_service.py        # Neo4j operations
│   │   ├── annotation_service.py   # Annotation service communication
│   │   └── graph_info_service.py   # Graph info generation
│   │
│   ├── api/                   # API endpoints
│   │   ├── upload.py          # Upload endpoints
│   │   ├── jobs.py            # Job management endpoints
│   │   ├── graph.py           # Graph info endpoints
│   │   └── admin.py           # Admin endpoints
│   │
│   └── utils/                 # Utilities
│       ├── file_utils.py      # File operations utilities
│       ├── schema_converter.py # Schema conversion utilities
│       └── helpers.py         # General helper functions
│
├── Makefile                   # Development and deployment commands
├── config.yaml               # Application configuration
├── requirements.txt          # Python dependencies
├── docker-compose.yml        # Production Docker setup
├── docker-compose.dev.yml    # Development Docker setup
├── example.env              # Environment variables template
└── README.md
```

## Features

### Core Functionality

- **Multi-Format Output**: Support for MeTTa-formatted knowledge graphs, Neo4j-compatible formats, and MORK database integration
- **Data Loading**: Upload CSV/JSON files with session-based processing and separate schema/configuration submission
- **Neo4j Integration**: CSV and Cypher file generation pipeline compatible with Neo4j's LOAD CSV functionality
- **MORK Integration**: Advanced knowledge representation and reasoning capabilities through MORK database backend
- **Schema Management**: Retrieve schema information formatted for annotation services and visualization tools
- **Job Tracking**: Comprehensive job history with metadata including node/edge counts, data size, and timestamps
- **Output Management**: Download job outputs as zip files or individual files

### Enhanced Capabilities

- **Graph Analytics**: Automatic generation of graph statistics including top entities, connections, and relationship patterns
- **Multi-Tenancy**: User-specific subgraph isolation using tenant IDs for nodes and edges
- **Annotation Service Integration**: Schema formatting optimized for graph annotation interfaces
- **Thread-Safe Operations**: File locking mechanisms preventing data loss during concurrent access
- **History Management**: Individual job deletion and complete history clearing capabilities
- **Session-Based Processing**: Support for multi-step workflows using session IDs
- **Makefile Workflow**: Streamlined development and deployment commands

## Installation & Setup

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Neo4j 4.x+ (for Neo4j backend)
- Apache HugeGraph Server (for HugeGraph backend)
- MORK database system (for MORK backend)
- Maven 3.6+ and Java 8+ (if building HugeGraph from source)

### 1. Clone the Repository

```bash
git clone https://github.com/rejuve-bio/custom-atomspace-builder
cd custom-atomspace-builder
```

### 2. Configuration

Create a `.env` file from the example template:

```bash
cp example.env .env
```

Edit the `.env` file with your specific configuration:

```bash
# ========================================
# API Configuration
# ========================================
API_PORT=8000

# ========================================
# Neo4j Database Configuration
# ========================================
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_HOST=localhost
NEO4J_PORT=7687
NEO4J_DATABASE=neo4j

# Neo4j Web Interface Ports
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687

# ========================================
# HugeGraph Configuration
# ========================================
HUGEGRAPH_HOST=localhost
HUGEGRAPH_PORT=8080
HUGEGRAPH_GRAPH=hugegraph

# HugeGraph Service Ports
HUGEGRAPH_REST_PORT=8080
HUGEGRAPH_GREMLIN_PORT=8182

# ========================================
# External Service URLs
# ========================================
ANNOTATION_SERVICE_URL=http://localhost:5800/annotation/load
ANNOTATION_SERVICE_TIMEOUT=300.0

# ========================================
# Application Settings
# ========================================
ENVIRONMENT=production
LOG_LEVEL=INFO
SESSION_TIMEOUT_HOURS=24
OUTPUT_DIR=./output
```

Update the `config.yaml` file for additional configuration:

```yaml
paths:
  hugegraph_loader: "/app/hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/hugegraph-loader.sh"
  output_dir: "./output"

cors:
  allow_origins: ["*"]
  allow_credentials: true
  allow_methods: ["*"]
  allow_headers: ["*"]

uploads:
  session_timeout: 24 # hours
```

### 3. Development Workflow with Makefile

The project includes a comprehensive Makefile for streamlined development and deployment operations:

### Available Make Commands

```bash
# Show all available commands
make help

# Development workflow
make build-dev      # Build all services in development mode
make up-dev         # Start all services in development mode
make logs-dev       # View development logs
make down-dev       # Stop development services

# Production workflow  
make build          # Build all services for production
make up             # Start all services in production mode
make logs           # View production logs
make down           # Stop all services

# Quick API-only operations
make up-api         # Start only the API service (production)
make up-api-dev     # Start only the API service (development)

# Maintenance operations
make rebuild        # Force rebuild and restart all services
make rebuild-dev    # Force rebuild and restart (development)
make clean          # Clean all containers and volumes (⚠️ deletes data)
make clean-dev      # Clean development containers and volumes
```

### Quick Start with Make

```bash
# 1. Set up environment
cp example.env .env
# Edit .env with your settings

# 2. Start development environment
make build-dev

# 3. View logs
make logs-dev

# 4. When making code changes (API only restart)
make up-api-dev

# 5. Clean shutdown
make down-dev
```

## Deployment

### Local Development

```bash
# Using Makefile (recommended)
make build-dev
```

### Production Development

```bash
# Using Makefile (recommended)
make build
```

### Docker Deployment

#### Development Deployment

```bash
# Quick start with Makefile
make build-dev

# Traditional method
docker compose -f docker-compose.dev.yml up -d
```

### Service URLs and Access

Once running, you can access:

- **API**: http://localhost:8000
  - Health check: http://localhost:8000/api/health
  - API documentation: http://localhost:8000/docs

- **Neo4j Browser**: http://localhost:7474
  - Username: `neo4j`
  - Password: From your `.env` file

- **HugeGraph**: http://localhost:8080
  - REST API: http://localhost:8080/graphs/hugegraph/conf
  - Gremlin WebSocket: ws://localhost:8182

- **Hubble UI**: http://localhost:8088 (if enabled)

## API Endpoints

### Session Management

- `POST /api/upload/create-session` - Create a new upload session
- `POST /api/upload/files` - Upload files to a session (session_id in request body)
- `GET /api/upload/status` - Get session status (session_id in request body)
- `DELETE /api/upload/files/{filename}` - Delete a file from session (session_id in request body)

### Data Loading

- `POST /api/load` - Load data files into selected backend (Neo4j, HugeGraph, or MORK)
- `POST /api/convert-schema` - Convert JSON schema to backend-specific format

### Job Management

- `GET /api/history` - Get complete job history with statistics
- `POST /api/select-job` - Select a specific job for operations
- `DELETE /api/history/{job_id}` - Remove specific job and delete associated files
- `DELETE /api/clear-history` - Remove all jobs and reset system

### Schema & Data Retrieval

- `GET /api/schema/` - Get schema for currently selected job
- `GET /api/schema/{job_id}` - Get schema information for specific job
- `GET /api/kg-info/{job_id}` - Get comprehensive graph information
- `GET /api/output/{job_id}` - Download all job outputs as zip
- `GET /api/output-file/{job_id}/{filename}` - Download specific file

### System

- `GET /api/health` - Health check endpoint
- `GET /api/config` - Get current configuration

## Backend Support

### Neo4j Backend
- CSV and Cypher file generation
- Direct database integration
- LOAD CSV functionality
- Multi-tenant support

### HugeGraph Backend  
- Apache TinkerPop Gremlin compatibility
- Distributed graph processing
- RESTful API integration
- High-performance analytics

### MORK Backend
- Advanced knowledge representation
- Logic-based reasoning capabilities
- Semantic query processing
- Integration with MeTTa language

## Usage Examples

### Loading Data with Multiple Backends

```bash
# Load data into Neo4j
curl -X POST "http://localhost:8000/api/load" \
  -F "files=@data.csv" \
  -F "config=$(cat struct.json)" \
  -F "schema_json=$(cat schema.json)" \
  -F "writer_type=neo4j" \
  -F "tenant_id=tenant_123" \
  -F "session_id=unique_session_456"

# Load data into MORK
curl -X POST "http://localhost:8000/api/load" \
  -F "files=@data.csv" \
  -F "config=$(cat struct.json)" \
  -F "schema_json=$(cat schema.json)" \
  -F "writer_type=mork" \
  -F "tenant_id=tenant_123" \
  -F "session_id=unique_session_456"
```

### Session-Based Workflow

```bash
# Step 1: Create session
curl -X POST "http://localhost:8000/api/upload/create-session"

# Step 2: Upload files with session ID
curl -X POST "http://localhost:8000/api/upload-files" \
  -F "files=@data1.csv" \
  -F "files=@data2.csv" \
  -F "session_id=unique_session_456"

# Step 3: Submit schema for the same session
curl -X POST "http://localhost:8000/api/submit-schema" \
  -F "schema=$(cat schema.json)" \
  -F "config=$(cat config.json)" \
  -F "session_id=unique_session_456" \
  -F "writer_type=mork"
```

### Development Workflow

```bash
# Start development environment
make up-dev

# Make code changes and restart only API
make up-api-dev

# View logs for debugging
make logs-dev

# Clean rebuild when needed
make rebuild-dev

# Stop everything
make down-dev
```

## Multi-Tenancy

The system implements robust multi-tenancy across all backends:

- Each node and edge is tagged with a tenant ID
- Complete subgraph isolation in shared database instances
- User-specific data separation while maintaining performance
- Queries automatically filtered by tenant context
- Session-based isolation for concurrent operations

## Thread Safety

Enhanced thread safety implementation:

- File locking prevents data loss during concurrent access
- Atomic operations for multi-file processing
- Session-based isolation for parallel workflows
- Queue-based job processing for high-load scenarios
- Automatic retry mechanisms for lock conflicts

## Error Handling

Comprehensive error handling includes:

- Thread-safe file operations with automatic retry
- Graceful handling of job deletion with automatic selection updates
- Transaction rollback for data integrity
- Session validation and timeout management
- Detailed error messages for debugging

## Testing

The system has been tested with:

- Large-scale datasets for performance validation
- Concurrent user scenarios with session isolation
- Multi-tenant isolation verification across all backends
- Integration testing with annotation services
- Thread safety validation under high load
- MORK backend integration and performance testing

## Troubleshooting

### Using Makefile Commands

```bash
# Check service status
make logs-dev

# Restart specific service  
make up-api-dev

# Clean start (removes all data)
make clean-dev
make up-dev

# View all available commands
make help
```

### Common Issues

1. **Port conflicts**: Change ports in `.env` file
2. **Permission issues**: Ensure Docker has proper permissions
3. **Memory issues**: Adjust memory settings in `.env` for development
4. **Build failures**: Use `make rebuild-dev` to force rebuild

## Roadmap

- [x] Neo4j backend integration for Custom AtomSpace Builder
- [x] Multi-tenancy support with tenant IDs
- [x] Docker containerization
- [x] Thread-safe file operations
- [x] Annotation service integration
- [x] Session-based processing support
- [x] MORK database integration
- [x] Makefile-based development workflow
- [ ] Deploy beta version with user authentication and feedback collection
- [ ] Database storage for metadata (replacing static JSON)
- [ ] Integrate automated schema inference from multiple data formats
- [ ] Build real-time validation and quality assessment pipeline
- [ ] Implement containerized deployment strategy for all backends
- [ ] Optimize performance for concurrent users and large datasets
- [ ] AWS deployment templates
- [ ] Advanced graph analytics and ML integration

## License

This project maintains the same license as the original Apache HugeGraph Toolchain project.

## Acknowledgments

- Apache HugeGraph Community
- Neo4j Community
- MORK Database Development Team
- SingularityNET for MeTTa language specification
- FastAPI framework contributors

---

For issues and feature requests, please create an issue in the repository.
