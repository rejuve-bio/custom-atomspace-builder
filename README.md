# Custom Atomspace Builder API

The Custom AtomSpace Builder is a comprehensive graph processing system that transforms structured tabular data into MeTTa-formatted knowledge graphs or Neo4j-compatible formats. Built on Apache HugeGraph Loader with custom modifications, it provides a complete pipeline for data ingestion, schema transformation, and graph generation with support for multiple output formats including direct Neo4j integration.

## Overview

This project provides a flexible graph data loading and transformation pipeline with:
- RESTful API interface for data loading operations
- Multi-backend support (Neo4j and HugeGraph) with configurable writer system
- Automatic MeTTa language representation generation for logic-based graph processing
- Multi-tenancy support with tenant-based graph isolation
- Comprehensive job management with history tracking
- Schema conversion and transformation utilities
- Integration with annotation services for AtomSpace interaction
- Thread-safe file operations for concurrent processing
- Direct Neo4j integration with CSV and Cypher file generation

## Features

### Core Functionality
- **Multi-Format Output**: Support for MeTTa-formatted knowledge graphs and Neo4j-compatible formats
- **Data Loading**: Upload CSV/JSON files with session-based processing and separate schema/configuration submission
- **Neo4j Integration**: CSV and Cypher file generation pipeline compatible with Neo4j's LOAD CSV functionality
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

## Current Deployment

The service is currently deployed on:
- **Server**: Bizon server
- **URL**: http://100.67.47.42:8001
- **API Documentation**: Available at the endpoints listed below

## Installation & Setup

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- Neo4j 4.x+ (for Neo4j backend)
- Apache HugeGraph Server (for HugeGraph backend)
- Maven 3.6+ and Java 8+ (if building HugeGraph from source)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd custom-atomspace-builder
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the project root:

```bash
# === Database credentials ===
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_HOST=localhost
NEO4J_PORT=7687
NEO4J_DATABASE=neo4j

# === HugeGraph settings ===
HUGEGRAPH_HOST=localhost
HUGEGRAPH_PORT=8080
HUGEGRAPH_GRAPH=hugegraph

# === Service URLs ===
ANNOTATION_SERVICE_URL=http://<ANNOTATION-HOST>:5800/annotation/load
ANNOTATION_SERVICE_TIMEOUT=300.0
```

Update the `config.yaml` file for additional configuration:

```yaml
paths:
  hugegraph_loader: "./hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/hugegraph-loader.sh"
  output_dir: "./output"

cors:
  allow_origins: ["*"]
  allow_credentials: true
  allow_methods: ["*"]
  allow_headers: ["*"]

uploads:
  session_timeout: 2 # hours
```

### 4. Run Database Instances

**For Neo4j:**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password_here \
  neo4j:latest
```

**For HugeGraph:**
```bash
docker run -d \
  -p 8080:8080 -p 8182:8182 \
  --name hugegraph \
  hugegraph/hugegraph
```
### 5. Build The Project
```
# Build the project (skip tests and checks for faster build)
mvn clean install -pl hugegraph-client,hugegraph-loader -am \
    -Dmaven.javadoc.skip=true \
    -DskipTests \
    -Dcheckstyle.skip=true \
    -Deditorconfig.skip=true

```
## Deployment

### Local Development

```bash
# Start the API server
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

## API Endpoints

### Data Loading
- `POST /api/load` - Load data files with configurable writer type and session ID
- `POST /api/upload-files` - Upload input files separately with session tracking
- `POST /api/submit-schema` - Submit schema/configuration for a session
- `POST /api/convert-schema` - Convert schema definitions

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

## Usage Examples

### Loading Data with Session ID

```bash
curl -X POST "http://100.67.47.42:8001/api/load" \
  -F "files=@data.csv" \
  -F "config=$(cat struct.json)" \
  -F "schema_json=$(cat schema.json)" \
  -F "writer_type=neo4j" \
  -F "tenant_id=tenant_123" \
  -F "session_id=unique_session_456"
```

### Session-Based Workflow

```bash
# Step 1: Upload files with session ID
curl -X POST "http://100.67.47.42:8001/api/upload-files" \
  -F "files=@data1.csv" \
  -F "files=@data2.csv" \
  -F "session_id=unique_session_456"

# Step 2: Submit schema for the same session
curl -X POST "http://100.67.47.42:8001/api/submit-schema" \
  -F "schema=$(cat schema.json)" \
  -F "config=$(cat config.json)" \
  -F "session_id=unique_session_456" \
  -F "writer_type=neo4j"
```

### Getting Schema Information

```bash
# Get schema for currently selected job
curl "http://100.67.47.42:8001/api/schema/"

# Get schema for specific job
curl "http://100.67.47.42:8001/api/schema/7af69710-cb5e-4eec-a46d-4dcca77c9111"
```

### Managing Job History

```bash
# Delete specific job
curl -X DELETE "http://100.67.47.42:8001/api/history/b2923344-ecd3-4489-994b-aa3cc1635d94"

# Clear all history
curl -X DELETE "http://100.67.47.42:8001/api/clear-history"
```

## Response Formats

### Schema Response Structure
```json
{
  "job_id": "string",
  "nodes": [
    {
      "id": "entity_type",
      "name": "entity_type",
      "category": "entity",
      "inputs": [
        {
          "label": "property_name",
          "name": "property_name",
          "inputType": "input"
        }
      ]
    }
  ],
  "edges": [
    {
      "id": "string",
      "source": "entity_type",
      "target": "entity_type",
      "label": "relationship_type"
    }
  ]
}
```

### Job History Entry Structure
```json
{
  "job_id": "string",
  "node_count": "number",
  "edge_count": "number",
  "dataset_count": "number",
  "data_size": "string",
  "imported_on": "timestamp",
  "top_entities": [{"name": "string", "count": "number"}],
  "top_connections": [{"name": "string", "count": "number"}],
  "frequent_relationships": [{"entities": ["string"], "count": "number"}],
  "schema": {
    "nodes": [{"data": {"id": "string", "properties": ["string"]}}],
    "edges": [{"data": {"source": "string", "target": "string", "possible_connections": ["string"]}}]
  }
}
```

## Multi-Tenancy

The system implements robust multi-tenancy:
- Each node and edge is tagged with a tenant ID
- Complete subgraph isolation in shared Neo4j instances
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
- Multi-tenant isolation verification
- Integration testing with annotation services
- Thread safety validation under high load

## Roadmap

### Completed
- [x] Neo4j backend integration for Custom AtomSpace Builder
- [x] Multi-tenancy support with tenant IDs
- [x] Docker containerization
- [x] Ansible deployment scripts
- [x] Thread-safe file operations
- [x] Annotation service integration
- [x] Comprehensive API documentation
- [x] Session-based processing support
- [ ] Deploy beta version with user authentication and feedback collection
- [ ] Database storage for metadata (replacing static JSON)
- [ ] Integrate automated schema inference from multiple data formats
- [ ] Build real-time validation and quality assessment pipeline
- [ ] Extend compatibility to MORK database system
- [ ] Implement containerized deployment strategy for all backends
- [ ] Optimize performance for concurrent users and large datasets
- [ ] AWS deployment templates
- [ ] Advanced graph analytics and ML integration

## License

This project maintains the same license as the original Apache HugeGraph Toolchain project.

## Acknowledgments

- Apache HugeGraph Community
- Neo4j Community
- SingularityNET for MeTTa language specification
- FastAPI framework contributors

---

For issues and feature requests, please create an issue in the repository.