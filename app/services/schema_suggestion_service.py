"""Schema suggestion service using LLM."""

import asyncio
from copy import deepcopy
import json
import os
import re
from typing import Any, Dict, List
import httpx
from ..models.schemas import DataSource, SuggestedSchema
from ..config import settings



class SchemaSuggestionService:
    """Service for generating schema suggestions using LLM."""
    
    def __init__(self):
        # You can configure different LLM providers here
        self.llm_provider =  settings.llm_provider
        self.api_key = settings.llm_api_key
        self.prompt_file = os.path.join(os.path.dirname(__file__), "..", "prompts", "schema_suggestion_v2.txt")
        
    async def suggest_schema(self, data_sources: List[DataSource]):
        """Generate schema suggestion from data sources."""
        
        # Create the prompt
        prompt = self._create_prompt(data_sources)
        
        # Get LLM response
        if self.llm_provider == "mock":
            schema_json = self._mock_llm_response(data_sources)
        elif self.llm_provider == "openai":
            schema_json = await self._call_openai(prompt)
        elif self.llm_provider == "anthropic":
            schema_json = await self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        
        # Parse and validate the response
        try:
            schema_data = json.loads(schema_json)
            schema_data = self._normalize_schema(schema_data)
            return {"schema": schema_data}
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            # Return a basic fallback schema
            raise Exception("Failed to parse schema suggestion from LLM response") from e
    
    def _create_prompt(self, data_sources: List[DataSource]) -> str:
        """Create the LLM prompt with data sources."""
        
        # Load the prompt template from file
        try:
            with open(self.prompt_file, 'r') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            print(f"Warning: Prompt file not found at {self.prompt_file}, using fallback prompt")
            prompt_template = self._get_fallback_prompt()
        
        # Add the data sources to the prompt
        data_sources_json = []
        for ds in data_sources:
            ds_dict = {
                "id": ds.id,
                "file": {
                    "name": ds.file.name,
                    "size": ds.file.size,
                    "type": ds.file.type
                },
                "columns": ds.columns,
                "sampleRow": ds.sampleRow
            }
            data_sources_json.append(ds_dict)
        
        prompt = prompt_template + "\n\n" + json.dumps(data_sources_json, indent=2)
        
        return prompt
    
    def _normalize_schema(self, schema):
        schema = deepcopy(schema)

        # 1. Ensure node IDs match their table values
        table_to_id = {}
        for node in schema["nodes"]:
            node["id"] = node["data"]["table"]
            table_to_id[node["data"]["name"].lower()] = node["id"]

        # 2. Merge edges between same source/target
        merged_edges = {}
        for edge in schema["edges"]:
            src_id = table_to_id.get(edge["source"], edge["source"])
            tgt_id = table_to_id.get(edge["target"], edge["target"])

            # Normalize source/target IDs in edges
            edge["source"] = src_id
            edge["target"] = tgt_id

            key = (src_id, tgt_id)
            if key not in merged_edges:
                merged_edges[key] = {
                    "id": f"{src_id}-{tgt_id}",
                    "type": "relation",
                    "source": src_id,
                    "target": tgt_id,
                    "data": {}
                }

            # Merge all connection types inside data
            for conn_type, conn_data in edge["data"].items():
                merged_edges[key]["data"][conn_type] = conn_data

        # 3. Detect reversed edges and merge them into the correct edge
        for (src, tgt), edge in list(merged_edges.items()):
            reverse_key = (tgt, src)
            if reverse_key in merged_edges and reverse_key != (src, tgt):
                reverse_edge = merged_edges.pop(reverse_key)
                for conn_type, conn_data in reverse_edge["data"].items():
                    conn_data["reversed"] = True
                    edge["data"][conn_type] = conn_data

        schema["edges"] = list(merged_edges.values())
        return schema
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file is not found."""
        return """Generate a knowledge graph schema from the provided data sources. 
        Return a JSON object with 'nodes' and 'edges' arrays following the specified interfaces.
        Analyze the data sources and create appropriate nodes and relationships:"""
    
    def _mock_llm_response(self, data_sources: List[DataSource]) -> str:
        """Generate a mock response for testing."""
        
        nodes = []
        edges = []
        node_positions = [(100, 100), (400, 100), (700, 100), (250, 300), (550, 300)]
        
        # Create nodes from data sources that look like node files
        for i, ds in enumerate(data_sources):
            if "nodes_" in ds.file.name.lower() or not any("edges_" in other_ds.file.name.lower() for other_ds in data_sources):
                # Extract entity type from filename or use generic
                entity_type = ds.file.name.replace("nodes_", "").replace(".csv", "").title()
                if not entity_type or entity_type == ds.file.name:
                    entity_type = f"Entity{i+1}"
                
                # Create properties from columns
                properties = {}
                for col in ds.columns:
                    prop_type = self._infer_column_type(col, ds.sampleRow[ds.columns.index(col)] if ds.columns.index(col) < len(ds.sampleRow) else "")
                    properties[col] = {
                        "col": col,
                        "type": prop_type,
                        "checked": True
                    }
                
                # Determine primary key
                primary_key = "id" if "id" in ds.columns else ds.columns[0] if ds.columns else None
                
                node = {
                    "id": ds.id,
                    "type": "entity",
                    "position": {"x": node_positions[i % len(node_positions)][0], "y": node_positions[i % len(node_positions)][1]},
                    "data": {
                        "name": entity_type,
                        "table": ds.id,
                        "primaryKey": primary_key,
                        "properties": properties
                    }
                }
                nodes.append(node)
        
        # Create edges from data sources that look like edge files
        edge_counter = 1
        for ds in data_sources:
            if "edges_" in ds.file.name.lower():
                # Try to extract relationship info from filename
                # Format: edges_source_target_relationship.csv
                filename_parts = ds.file.name.replace("edges_", "").replace(".csv", "").split("_")
                
                if len(filename_parts) >= 3:
                    source_type = filename_parts[0]
                    target_type = filename_parts[1] 
                    relationship_name = "_".join(filename_parts[2:])
                    
                    # Find matching nodes
                    source_node = None
                    target_node = None
                    
                    for node in nodes:
                        node_name = node["data"]["name"].lower()
                        if source_type.lower() in node_name or node_name in source_type.lower():
                            source_node = node["id"]
                        if target_type.lower() in node_name or node_name in target_type.lower():
                            target_node = node["id"]
                    
                    if source_node and target_node:
                        # Create properties from edge columns
                        edge_properties = {}
                        for col in ds.columns:
                            if col.lower() not in ["source", "target", "id"]:
                                prop_type = self._infer_column_type(col, ds.sampleRow[ds.columns.index(col)] if ds.columns.index(col) < len(ds.sampleRow) else "")
                                edge_properties[col] = {
                                    "col": col,
                                    "type": prop_type,
                                    "checked": True
                                }
                        
                        edge = {
                            "id": f"edge_{edge_counter}",
                            "type": "relation",
                            "source": source_node,
                            "target": target_node,
                            "name": relationship_name.replace("_", " ").title(),
                            "data": {
                                relationship_name: {
                                    "name": relationship_name.replace("_", " ").title(),
                                    "table": ds.id,
                                    "source": "source" if "source" in ds.columns else ds.columns[1] if len(ds.columns) > 1 else None,
                                    "target": "target" if "target" in ds.columns else ds.columns[2] if len(ds.columns) > 2 else None,
                                    "properties": edge_properties
                                }
                            }
                        }
                        edges.append(edge)
                        edge_counter += 1
        
        schema = {
            "nodes": nodes,
            "edges": edges
        }
        
        return json.dumps(schema, indent=2)
    
    def _infer_column_type(self, column_name: str, sample_value: str) -> str:
        """Infer column type from name and sample value."""
        column_lower = column_name.lower()
        
        # Check for numeric types
        if any(word in column_lower for word in ["id", "count", "number", "quantity", "amount"]):
            return "int"
        
        if any(word in column_lower for word in ["price", "cost", "rate", "percentage", "score"]):
            return "double"
        
        # Try to parse sample value
        if sample_value:
            try:
                if "." in sample_value:
                    float(sample_value)
                    return "double"
                else:
                    int(sample_value)
                    return "int"
            except ValueError:
                pass
        
        return "text"

    def _clean_json_response(self, text: str):
        # Remove triple backticks and optional 'json'
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        return cleaned
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API with retry on transient errors."""
        max_retries = 5
        backoff = 1  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4.1",
                            "input": prompt,
                            "temperature": 0
                        }
                    )

                if response.status_code != 200:
                    raise Exception(
                        f"OpenAI API call failed with status {response.status_code}: {response.text}"
                    )

                result = response.json()
                return self._clean_json_response(
                    result["output"][0]["content"][0]["text"]
                )

            except (httpx.RequestError, httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt == max_retries:
                    raise Exception(f"OpenAI API request failed after {max_retries} attempts: {str(e)}")
                wait_time = backoff * (2 ** (attempt - 1))
                print(f"Attempt {attempt} failed ({e}), retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

            except Exception as e:
                # Don't retry on parsing or other non-network errors
                raise Exception(f"OpenAI API call failed: {str(e)}")
    
    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        # Implement Anthropic API call
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-sonnet-20240229",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            result = response.json()
            return result["content"][0]["text"]
    
    def _create_fallback_schema(self, data_sources: List[DataSource]) -> SuggestedSchema:
        """Create a basic fallback schema if LLM fails."""
        nodes = []
        edges = []
        
        # Create a simple node for each data source
        for i, ds in enumerate(data_sources):
            properties = {}
            for col in ds.columns:
                properties[col] = {
                    "col": col,
                    "type": "text",
                    "checked": True
                }
            
            node = {
                "id": ds.id,
                "type": "entity",
                "position": {"x": 100 + i * 200, "y": 100},
                "data": {
                    "name": ds.file.name.replace(".csv", ""),
                    "table": ds.id,
                    "primaryKey": ds.columns[0] if ds.columns else None,
                    "properties": properties
                }
            }
            nodes.append(node)
        
        return SuggestedSchema(nodes=nodes, edges=edges)


# Global service instance
schema_suggestion_service = SchemaSuggestionService()