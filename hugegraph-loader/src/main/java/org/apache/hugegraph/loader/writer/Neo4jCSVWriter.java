package org.apache.hugegraph.loader.writer;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

import org.apache.hugegraph.loader.builder.Record;
import org.apache.hugegraph.structure.graph.Edge;
import org.apache.hugegraph.structure.graph.Vertex;

public class Neo4jCSVWriter {
    
    private static final String CSV_DELIMITER = "|";
    private static final String ARRAY_DELIMITER = ";";
    
    private final String OUTPUT_DIR;
    private final String JOB_ID;
    private final Map<String, Set<String>> nodeHeaders = new ConcurrentHashMap<>();
    private final Map<String, Set<String>> edgeHeaders = new ConcurrentHashMap<>();
    private final Map<String, String> edgeNodeTypes = new ConcurrentHashMap<>();
    private final int batchSize = 10000;
    
    public Neo4jCSVWriter(String outputDir, String jobId) {
        this.OUTPUT_DIR = outputDir;
        this.JOB_ID = jobId;
        try {
            Files.createDirectories(Paths.get(OUTPUT_DIR));
        } catch (IOException e) {
            throw new RuntimeException("Failed to create output directory", e);
        }
    }
    
    /**
     * Write nodes to CSV format compatible with Neo4j
     */
    public void writeNodes(List<Record> records) {
        Map<String, List<Map<String, Object>>> nodesByLabel = groupNodesByLabel(records);
        
        for (Map.Entry<String, List<Map<String, Object>>> entry : nodesByLabel.entrySet()) {
            String label = entry.getKey();
            List<Map<String, Object>> nodes = entry.getValue();
            
            String csvPath = OUTPUT_DIR + "/nodes_" + label + ".csv";
            String cypherPath = OUTPUT_DIR + "/nodes_" + label + ".cypher";
            
            try {
                writeNodeCSV(label, nodes, csvPath);
                writeNodeCypher(label, csvPath, cypherPath);
            } catch (IOException e) {
                throw new RuntimeException("Failed to write nodes for label: " + label, e);
            }
        }
    }
    
    /**
     * Write edges to CSV format compatible with Neo4j
     */
    public void writeEdges(List<Record> records) {
        Map<String, List<Map<String, Object>>> edgesByType = groupEdgesByType(records);
        
        for (Map.Entry<String, List<Map<String, Object>>> entry : edgesByType.entrySet()) {
            String edgeKey = entry.getKey();
            List<Map<String, Object>> edges = entry.getValue();
            
            String csvPath = OUTPUT_DIR + "/edges_" + edgeKey + ".csv";
            String cypherPath = OUTPUT_DIR + "/edges_" + edgeKey + ".cypher";
            
            try {
                writeEdgeCSV(edgeKey, edges, csvPath);
                writeEdgeCypher(edgeKey, csvPath, cypherPath);
            } catch (IOException e) {
                throw new RuntimeException("Failed to write edges for type: " + edgeKey, e);
            }
        }
    }
    
    private void writeNodeCSV(String label, List<Map<String, Object>> nodes, String csvPath) throws IOException {
        Set<String> headers = new HashSet<>();
        headers.add("id");
        
        // Collect all possible headers
        for (Map<String, Object> node : nodes) {
            headers.addAll(node.keySet());
        }
        
        List<String> sortedHeaders = new ArrayList<>(headers);
        Collections.sort(sortedHeaders);
        
        try (FileWriter writer = new FileWriter(csvPath)) {
            // Write header
            writer.write(String.join(CSV_DELIMITER, sortedHeaders) + "\n");
            
            // Write data
            for (Map<String, Object> node : nodes) {
                List<String> values = new ArrayList<>();
                for (String header : sortedHeaders) {
                    Object value = node.get(header);
                    values.add(preprocessValue(value));
                }
                writer.write(String.join(CSV_DELIMITER, values) + "\n");
            }
        }
    }
    
    private void writeEdgeCSV(String edgeKey, List<Map<String, Object>> edges, String csvPath) throws IOException {
        Set<String> headers = new HashSet<>();
        headers.addAll(Arrays.asList("source_id", "target_id", "label", "source_type", "target_type"));
        
        // Collect all possible headers
        for (Map<String, Object> edge : edges) {
            headers.addAll(edge.keySet());
        }
        
        List<String> sortedHeaders = new ArrayList<>(headers);
        Collections.sort(sortedHeaders);
        
        try (FileWriter writer = new FileWriter(csvPath)) {
            // Write header
            writer.write(String.join(CSV_DELIMITER, sortedHeaders) + "\n");
            
            // Write data
            for (Map<String, Object> edge : edges) {
                List<String> values = new ArrayList<>();
                for (String header : sortedHeaders) {
                    Object value = edge.get(header);
                    values.add(preprocessValue(value));
                }
                writer.write(String.join(CSV_DELIMITER, values) + "\n");
            }
        }
    }
    
    private void writeNodeCypher(String label, String csvPath, String cypherPath) throws IOException {
        String absolutePath = new File(csvPath).getAbsolutePath();
        String csvFileName = this.JOB_ID + "/" + new File(csvPath).getName();
        
        String cypherQuery = String.format(
            "CALL apoc.periodic.iterate(\n" +
            "  \"LOAD CSV WITH HEADERS FROM 'file:///%s' AS row FIELDTERMINATOR '%s' RETURN row\",\n" +
            "  \"CREATE (n:%s {id: row.id, tenant_id:'%s'}) SET n += apoc.map.removeKeys(row, ['id'])\",\n" +
            "  {batchSize:1000, parallel:true, concurrency:4}\n" +
            ") YIELD batches, total RETURN batches, total;",
            csvFileName, CSV_DELIMITER, label, this.JOB_ID
        );
        
        try (FileWriter writer = new FileWriter(cypherPath)) {
            writer.write(cypherQuery);
        }
    }
    
    private void writeEdgeCypher(String edgeKey, String csvPath, String cypherPath) throws IOException {
        String absolutePath = new File(csvPath).getAbsolutePath();
        String csvFileName = this.JOB_ID + "/" + new File(csvPath).getName();
        
        // Extract edge information from key (format: label_sourceType_targetType)
        String[] parts = edgeKey.split("_");
        String edgeLabel = parts[0];
        String sourceType = parts[1];
        String targetType = parts[2];
        
        String cypherQuery = String.format(
            "CALL apoc.periodic.iterate(\n" +
            "  \"LOAD CSV WITH HEADERS FROM 'file:///%s' AS row FIELDTERMINATOR '%s' RETURN row\",\n" +
            "  \"MATCH (source:%s {id: row.source_id, tenant_id:'%s'}) MATCH (target:%s {id: row.target_id, tenant_id:'%s'}) \" +\n" +
            "  \"CREATE (source)-[r:%s {tenant_id:'%s'}]->(target) \" +\n" +
            "  \"SET r += apoc.map.removeKeys(row, ['source_id', 'target_id', 'label', 'source_type', 'target_type'])\",\n" +
            "  {batchSize:1000}\n" +
            ") YIELD batches, total RETURN batches, total;",
            csvFileName, CSV_DELIMITER, sourceType, this.JOB_ID, targetType, this.JOB_ID, edgeLabel, this.JOB_ID
        );
        
        try (FileWriter writer = new FileWriter(cypherPath)) {
            writer.write(cypherQuery);
        }
    }
    
    private String preprocessValue(Object value) {
        if (value == null) {
            return "";
        }
        
        String stringValue = value.toString();
        
        // Remove problematic characters
        stringValue = stringValue.replace(CSV_DELIMITER, "")
                                .replace(ARRAY_DELIMITER, " ")
                                .replace("'", "")
                                .replace("\"", "");
        
        return stringValue;
    }
    
    private String preprocessId(String id) {
        return id.toLowerCase()
                .replace(" ", "_")
                .replace(":", "_")
                .trim();
    }
    
    private Map<String, List<Map<String, Object>>> groupNodesByLabel(List<Record> records) {
        Map<String, List<Map<String, Object>>> result = new HashMap<>();
        
        for (Record record : records) {
            Vertex vertex = (Vertex) record.element();
            String label = vertex.label().toLowerCase();
            
            Map<String, Object> nodeData = new HashMap<>();
            nodeData.put("id", preprocessId(vertex.id().toString()));
            nodeData.putAll(vertex.properties());
            
            result.computeIfAbsent(label, k -> new ArrayList<>()).add(nodeData);
        }
        
        return result;
    }
    
    private Map<String, List<Map<String, Object>>> groupEdgesByType(List<Record> records) {
        Map<String, List<Map<String, Object>>> result = new HashMap<>();
        
        for (Record record : records) {
            Edge edge = (Edge) record.element();
            String label = edge.label().toLowerCase();
            String sourceLabel = edge.sourceLabel().toLowerCase();
            String targetLabel = edge.targetLabel().toLowerCase();
            
            String edgeKey = label + "_" + sourceLabel + "_" + targetLabel;
            
            Map<String, Object> edgeData = new HashMap<>();
            edgeData.put("source_id", preprocessId(edge.sourceId().toString()));
            edgeData.put("target_id", preprocessId(edge.targetId().toString()));
            edgeData.put("label", label);
            edgeData.put("source_type", sourceLabel);
            edgeData.put("target_type", targetLabel);
            edgeData.putAll(edge.properties());
            
            result.computeIfAbsent(edgeKey, k -> new ArrayList<>()).add(edgeData);
        }
        
        return result;
    }
}