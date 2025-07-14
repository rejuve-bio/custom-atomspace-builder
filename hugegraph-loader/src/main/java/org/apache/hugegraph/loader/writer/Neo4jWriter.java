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
    
    private static final String OUTPUT_DIR = "/home/developer/Desktop/neo4j_output";
    private static final String CSV_DELIMITER = "|";
    private static final String ARRAY_DELIMITER = ";";
    
    private final Map<String, Set<String>> nodeHeaders = new ConcurrentHashMap<>();
    private final Map<String, Set<String>> edgeHeaders = new ConcurrentHashMap<>();
    private final Map<String, String> edgeNodeTypes = new ConcurrentHashMap<>();
    private final int batchSize = 10000;
    
    public Neo4jCSVWriter() {
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
    
    
    private void writeNodeCypher(String label, String csvPath, String cypherPath) throws IOException {
        String absolutePath = new File(csvPath).getAbsolutePath();
        
        String cypherQuery = String.format(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:%s) REQUIRE n.id IS UNIQUE;\n\n" +
            "CALL apoc.periodic.iterate(\n" +
            "  \"LOAD CSV WITH HEADERS FROM 'file:///%s' AS row FIELDTERMINATOR '%s' RETURN row\",\n" +
            "  \"MERGE (n:%s {id: row.id}) SET n += apoc.map.removeKeys(row, ['id'])\",\n" +
            "  {batchSize:1000, parallel:true, concurrency:4}\n" +
            ") YIELD batches, total RETURN batches, total;",
            label, absolutePath, CSV_DELIMITER, label
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
    
}