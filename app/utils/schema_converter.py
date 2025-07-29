"""Schema conversion utilities for HugeGraph."""

from typing import Union, Dict, Any
from ..models.schemas import SchemaDefinition


def json_to_groovy(schema_json: Union[Dict, SchemaDefinition]) -> str:
    """Convert JSON schema definition to Groovy format for HugeGraph."""
    if isinstance(schema_json, dict):
        schema = SchemaDefinition(**schema_json)
    else:
        schema = schema_json
    
    groovy_lines = []
    
    # Generate property key definitions
    for prop in schema.property_keys:
        line = f'schema.propertyKey("{prop.name}").as{prop.type.capitalize()}()'
        if prop.cardinality:
            line += f'.cardinality("{prop.cardinality}")'
        if prop.options:
            for opt_name, opt_value in prop.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    groovy_lines.append("")
    
    # Generate vertex label definitions
    for vertex in schema.vertex_labels:
        line = f'schema.vertexLabel("{vertex.name}")'
        if vertex.id_strategy:
            if vertex.id_strategy == "primary_key":
                line += '.useCustomizeStringId()'
            elif vertex.id_strategy == "customize_number":
                line += '.useCustomizeNumberId()'
            elif vertex.id_strategy == "customize_string":
                line += '.useCustomizeStringId()'
            elif vertex.id_strategy == "automatic":
                line += '.useAutomaticId()'
        if vertex.properties:
            props_str = ', '.join([f'"{prop}"' for prop in vertex.properties])
            line += f'.properties({props_str})'
        if vertex.primary_keys:
            keys_str = ', '.join([f'"{key}"' for key in vertex.primary_keys])
            line += f'.primaryKeys({keys_str})'
        if vertex.nullable_keys:
            keys_str = ', '.join([f'"{key}"' for key in vertex.nullable_keys])
            line += f'.nullableKeys({keys_str})'
        if vertex.options:
            for opt_name, opt_value in vertex.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    groovy_lines.append("")
    
    # Generate edge label definitions
    for edge in schema.edge_labels:
        line = f'schema.edgeLabel("{edge.name}")'
        line += f'.sourceLabel("{edge.source_label}")'
        line += f'.targetLabel("{edge.target_label}")'
        if edge.properties:
            props_str = ', '.join([f'"{prop}"' for prop in edge.properties])
            line += f'.properties({props_str})'
        if edge.sort_keys:
            keys_str = ', '.join([f'"{key}"' for key in edge.sort_keys])
            line += f'.sortKeys({keys_str})'
        if edge.options:
            for opt_name, opt_value in edge.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    return '\n'.join(groovy_lines)


def generate_annotation_schema(schema_data: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """Generate annotation schema from schema data."""
    annotation_schema = {"job_id": job_id, "nodes": [], "edges": []}
    
    # Generate nodes from vertex labels
    for vertex in schema_data.get("vertex_labels", []):
        annotation_schema["nodes"].append({
            "id": vertex["name"],
            "name": vertex["name"],
            "category": "entity",
            "inputs": [{"label": prop, "name": prop, "inputType": "input"}
                      for prop in vertex.get("properties", [])]
        })
    
    # Generate edges from edge labels
    for i, edge in enumerate(schema_data.get("edge_labels", []), 1):
        annotation_schema["edges"].append({
            "id": str(i),
            "source": edge["source_label"],
            "target": edge["target_label"],
            "label": edge["name"]
        })
    
    return annotation_schema