package org.apache.hugegraph.loader.writer;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

import org.apache.hugegraph.loader.builder.Record;
import org.apache.hugegraph.structure.graph.Edge;
import org.apache.hugegraph.structure.graph.Vertex;

public class Neo4jCSVWriter {
    
    private static final String CSV_DELIMITER = "|";
    private static final String ARRAY_DELIMITER = ";";
    private static final String EDGE_KEY_DELIMITER = "_";
    
    private final String OUTPUT_DIR;
    private final String JOB_ID;
    
    // Use the same locking approach as MeTTaWriter
    private static final ConcurrentHashMap<String, Object> FILE_LOCKS = new ConcurrentHashMap<>();
    private final Map<String, EdgeInfo> edgeInfoMap = new ConcurrentHashMap<>();
    
    // Put the EdgeInfo class here as a private static nested class
    private static class EdgeInfo {
        final String label;
        final String sourceType;
        final String targetType;
        
        EdgeInfo(String label, String sourceType, String targetType) {
            this.label = label;
            this.sourceType = sourceType;
            this.targetType = targetType;
        }
        
        String getKey() {
            return label + EDGE_KEY_DELIMITER + sourceType + EDGE_KEY_DELIMITER + targetType;
        }
    }

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
                writeNodeCSVWithLock(label, nodes, csvPath);
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
                writeEdgeCSVWithLock(edgeKey, edges, csvPath);
                writeEdgeCypher(edgeKey, csvPath, cypherPath);
            } catch (IOException e) {
                throw new RuntimeException("Failed to write edges for type: " + edgeKey, e);
            }
        }
    }
    
    /**
     * Thread-safe node CSV writing using the same pattern as MeTTaWriter
     */
    private void writeNodeCSVWithLock(String label, List<Map<String, Object>> nodes, String csvPath) throws IOException {
        // Get or create a lock object for this file (same as MeTTaWriter)
        Object fileLock = FILE_LOCKS.computeIfAbsent(csvPath, k -> new Object());
        
        synchronized (fileLock) {
            try (RandomAccessFile file = new RandomAccessFile(csvPath, "rw");
                 FileChannel channel = file.getChannel();
                 FileLock lock = channel.lock()) {
                
                boolean isNewFile = file.length() == 0;
                
                // Move to the end of the file
                file.seek(file.length());
                
                // Collect all headers
                Set<String> headers = new HashSet<>();
                headers.add("id");
                for (Map<String, Object> node : nodes) {
                    headers.addAll(node.keySet());
                }
                
                List<String> sortedHeaders = new ArrayList<>(headers);
                Collections.sort(sortedHeaders);
                
                StringBuilder content = new StringBuilder();
                
                // Write header if new file
                if (isNewFile) {
                    content.append(String.join(CSV_DELIMITER, sortedHeaders)).append("\n");
                }
                
                // Write all data in one operation
                for (Map<String, Object> node : nodes) {
                    List<String> values = new ArrayList<>();
                    for (String header : sortedHeaders) {
                        Object value = node.get(header);
                        values.add(preprocessValue(value));
                    }
                    content.append(String.join(CSV_DELIMITER, values)).append("\n");
                }
                
                // Write the entire content at once
                file.write(content.toString().getBytes());
                
                // Force changes to be written to the disk
                channel.force(true);
            }
        }
    }
    
    /**
     * Thread-safe edge CSV writing using the same pattern as MeTTaWriter
     */
    private void writeEdgeCSVWithLock(String edgeKey, List<Map<String, Object>> edges, String csvPath) throws IOException {
        // Get or create a lock object for this file (same as MeTTaWriter)
        Object fileLock = FILE_LOCKS.computeIfAbsent(csvPath, k -> new Object());
        
        synchronized (fileLock) {
            try (RandomAccessFile file = new RandomAccessFile(csvPath, "rw");
                 FileChannel channel = file.getChannel();
                 FileLock lock = channel.lock()) {
                
                boolean isNewFile = file.length() == 0;
                
                // Move to the end of the file
                file.seek(file.length());
                
                // Collect all headers
                Set<String> headers = new HashSet<>();
                headers.addAll(Arrays.asList("source_id", "target_id", "label", "source_type", "target_type"));
                for (Map<String, Object> edge : edges) {
                    headers.addAll(edge.keySet());
                }
                
                List<String> sortedHeaders = new ArrayList<>(headers);
                Collections.sort(sortedHeaders);
                
                StringBuilder content = new StringBuilder();
                
                // Write header if new file
                if (isNewFile) {
                    content.append(String.join(CSV_DELIMITER, sortedHeaders)).append("\n");
                }
                
                // Write all data in one operation
                for (Map<String, Object> edge : edges) {
                    List<String> values = new ArrayList<>();
                    for (String header : sortedHeaders) {
                        Object value = edge.get(header);
                        values.add(preprocessValue(value));
                    }
                    content.append(String.join(CSV_DELIMITER, values)).append("\n");
                }
                
                // Write the entire content at once
                file.write(content.toString().getBytes());
                
                // Force changes to be written to the disk
                channel.force(true);
            }
        }
    }
    
    private void writeNodeCypher(String label, String csvPath, String cypherPath) throws IOException {
        String csvFileName = this.JOB_ID + "/" + new File(csvPath).getName();
        
        String cypherQuery = String.format(
            "CALL apoc.periodic.iterate(\n" +
            "  \"LOAD CSV WITH HEADERS FROM 'file:///%s' AS row FIELDTERMINATOR '%s' RETURN row\",\n" +
            "  \"CREATE (n:%s {id: row.id, tenant_id:'%s'}) SET n += apoc.map.removeKeys(row, ['id'])\",\n" +
            "  {batchSize:1000, parallel:true, concurrency:4}\n" +
            ") YIELD batches, total RETURN batches, total;",
            csvFileName, CSV_DELIMITER, label, this.JOB_ID
        );
        
        // Use the same locking approach for cypher files
        Object fileLock = FILE_LOCKS.computeIfAbsent(cypherPath, k -> new Object());
        
        synchronized (fileLock) {
            try (RandomAccessFile file = new RandomAccessFile(cypherPath, "rw");
                 FileChannel channel = file.getChannel();
                 FileLock lock = channel.lock()) {
                
                file.write(cypherQuery.getBytes());
                channel.force(true);
            }
        }
    }
    
    private void writeEdgeCypher(String edgeKey, String csvPath, String cypherPath) throws IOException {
        String csvFileName = this.JOB_ID + "/" + new File(csvPath).getName();
        
        // Get edge info from stored metadata
        EdgeInfo edgeInfo = edgeInfoMap.get(edgeKey);
        if (edgeInfo == null) {
            throw new RuntimeException("Edge info not found for key: " + edgeKey);
        }
        
        String cypherQuery = String.format(
            "CALL apoc.periodic.iterate(\n" +
            "  \"LOAD CSV WITH HEADERS FROM 'file:///%s' AS row FIELDTERMINATOR '%s' RETURN row\",\n" +
            "  \"MATCH (source:%s {id: row.source_id, tenant_id:'%s'}) MATCH (target:%s {id: row.target_id, tenant_id:'%s'}) \" +\n" +
            "  \"CREATE (source)-[r:%s {tenant_id:'%s'}]->(target) \" +\n" +
            "  \"SET r += apoc.map.removeKeys(row, ['source_id', 'target_id', 'label', 'source_type', 'target_type'])\",\n" +
            "  {batchSize:1000}\n" +
            ") YIELD batches, total RETURN batches, total;",
            csvFileName, CSV_DELIMITER, edgeInfo.sourceType, this.JOB_ID, edgeInfo.targetType, this.JOB_ID, edgeInfo.label, this.JOB_ID
        );
        
        // Use the same locking approach for cypher files
        Object fileLock = FILE_LOCKS.computeIfAbsent(cypherPath, k -> new Object());
        
        synchronized (fileLock) {
            try (RandomAccessFile file = new RandomAccessFile(cypherPath, "rw");
                 FileChannel channel = file.getChannel();
                 FileLock lock = channel.lock()) {
                
                file.write(cypherQuery.getBytes());
                channel.force(true);
            }
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
            String label = vertex.label();
            
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
            String label = edge.label();
            String sourceLabel = edge.sourceLabel();
            String targetLabel = edge.targetLabel();
            
            EdgeInfo edgeInfo = new EdgeInfo(label, sourceLabel, targetLabel);
            String edgeKey = edgeInfo.getKey();
            
            // Store edge info for later use
            edgeInfoMap.put(edgeKey, edgeInfo);
            
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