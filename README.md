# HugeGraph Loader API

A FastAPI-based REST API wrapper for Apache HugeGraph Loader with enhanced capabilities including MeTTa graph representation generation and comprehensive job management.

## Overview

This project extends the Apache HugeGraph Loader by providing:
- RESTful API interface for data loading operations
- Automatic MeTTa language representation generation for logic-based graph processing
- Job management and history tracking
- Schema conversion utilities (JSON to Groovy)
- Integration with annotation services
- Comprehensive output file management

## Features

### Core Functionality
- **Data Loading**: Upload CSV/JSON files and load them into HugeGraph
- **Schema Management**: Convert JSON schema definitions to HugeGraph Groovy format
- **Job Tracking**: Maintain history of all loading operations with metadata
- **Output Management**: Download job outputs as zip files or individual files

### Enhanced Capabilities
- **MeTTa Integration**: Generate MeTTa language representations for logic-based graph processing
- **Annotation Support**: Integration with external annotation services
- **Graph Analytics**: Generate comprehensive graph statistics and visualizations
- **History Management**: Clear history and manage job selections

## Installation & Setup

### Prerequisites
- Python 3.8+
- Maven 3.6+
- Java 8+
- Apache HugeGraph Server (running)

### 1. Clone and Build

```bash
# Clone the forked repository
git clone <your-forked-repo-url>
cd incubator-hugegraph-toolchain

# Build the project (skip tests and checks for faster build)
mvn clean install -pl hugegraph-client,hugegraph-loader -am \
    -Dmaven.javadoc.skip=true \
    -DskipTests \
    -Dcheckstyle.skip=true \
    -Deditorconfig.skip=true
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuration

Update the configuration variables in `app.py`:

```python
HUGEGRAPH_LOADER_PATH = "./hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/hugegraph-loader.sh"
HUGEGRAPH_HOST = "localhost"
HUGEGRAPH_PORT = "8080"
HUGEGRAPH_GRAPH = "hugegraph"
ANNOTATION_SERVICE_URL = "http://your-annotation-service:5800/annotation/load"
```

## Deployment

### Current Deployment Method

```bash
# Check if uvicorn is already running
ps aux | grep uvicorn

# Kill existing process if needed
kill <pid>

# Start the API server in background
nohup uvicorn app:app --host 0.0.0.0 --port 8000 --reload > uvicorn.log 2>&1 &
```

### Future: Docker Deployment (In Development)

We're working on containerizing the entire stack for easier deployment. Stay tuned for Docker Compose configuration.

## API Endpoints

### Data Loading
- `POST /api/load` - Load data files into HugeGraph
- `POST /api/convert-schema` - Convert JSON schema to Groovy format

### Job Management
- `GET /api/history` - Get job history
- `POST /api/select-job` - Select a specific job for operations
- `POST /api/clear-history` - Clear all job history

### Data Retrieval
- `GET /api/kg-info/{job_id}` - Get comprehensive graph information
- `GET /api/schema/{job_id}` - Get annotation schema
- `GET /api/output/{job_id}` - Download all job outputs as zip
- `GET /api/output-file/{job_id}/{filename}` - Download specific file

### System
- `GET /api/health` - Health check endpoint

## Usage Examples

### Loading Data

```bash
curl -X POST "http://localhost:8000/api/load" \
  -F "files=@data.csv" \
  -F "config=$(cat struct.json)" \
  -F "schema_json=$(cat schema.json)"
```

### Getting Graph Information

```bash
curl "http://localhost:8000/api/kg-info/"
```

### Schema Conversion

```bash
curl -X POST "http://localhost:8000/api/convert-schema" \
  -H "Content-Type: application/json" \
  -d @schema.json
```

## MeTTa Integration

This project includes a custom MeTTa writer that generates logic-based graph representations compatible with [SingularityNET's MeTTa language](https://metta-lang.dev/). 

The MeTTa representation provides:
- Logic-based graph querying capabilities
- Integration with AI reasoning systems
- Symbolic representation of graph structures
- Support for advanced graph analytics

## Schema Format

### Input Schema (JSON)
```json
{
  "property_keys": [
    {
      "name": "name",
      "type": "text",
      "cardinality": "single"
    }
  ],
  "vertex_labels": [
    {
      "name": "person",
      "properties": ["name", "age"],
      "primary_keys": ["name"]
    }
  ],
  "edge_labels": [
    {
      "name": "knows",
      "source_label": "person",
      "target_label": "person"
    }
  ]
}
```

### Output (Groovy)
```groovy
schema.propertyKey("name").asText().cardinality("single").ifNotExist().create();
schema.vertexLabel("person").properties("name", "age").primaryKeys("name").ifNotExist().create();
schema.edgeLabel("knows").sourceLabel("person").targetLabel("person").ifNotExist().create();
```

## Error Handling

The API provides comprehensive error handling:
- Graceful handling of missing job directories
- Empty history state management
- Robust file operation error handling
- Service integration timeout handling

## Contributing

This project is based on Apache HugeGraph Toolchain. Contributions are welcome for:
- MeTTa writer improvements
- Additional output formats
- Docker containerization
- Performance optimizations

## Roadmap

- [ ] Complete Docker containerization
- [ ] Enhanced MeTTa language features
- [ ] Real-time graph streaming capabilities
- [ ] Kubernetes deployment configurations

## License

This project maintains the same license as the original Apache HugeGraph Toolchain project.

## Acknowledgments

- Apache HugeGraph Community
- SingularityNET for MeTTa language specification
- FastAPI framework contributors

---

For issues and feature requests, please create an issue in the repository.
