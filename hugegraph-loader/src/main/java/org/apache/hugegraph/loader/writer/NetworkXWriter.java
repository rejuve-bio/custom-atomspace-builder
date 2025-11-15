package org.apache.hugegraph.loader.writer;  
  
import java.io.BufferedReader;  
import java.io.IOException;  
import java.io.InputStreamReader;  
import java.nio.file.Files;  
import java.nio.file.Paths;  
import java.util.*;  
import java.util.concurrent.ConcurrentHashMap;  
  
import org.apache.hugegraph.loader.builder.Record;  
import org.apache.hugegraph.structure.graph.Edge;  
import org.apache.hugegraph.structure.graph.Vertex;  
  
import com.fasterxml.jackson.databind.ObjectMapper;  
import com.fasterxml.jackson.databind.node.ObjectNode;  
import com.fasterxml.jackson.databind.node.ArrayNode;  
  
public class NetworkXWriter implements Writer {  
      
    private final String outputDir;  
    private final String jobId;  
    private final Map<String, Integer> nodeMapping = new ConcurrentHashMap<>();  
    private final Map<String, Integer> nodeCounters = new ConcurrentHashMap<>();  
    private final Map<String, Integer> edgeCounters = new ConcurrentHashMap<>();  
    private final List<Map<String, Object>> nodes = Collections.synchronizedList(new ArrayList<>());  
    private final List<Map<String, Object>> edges = Collections.synchronizedList(new ArrayList<>());  
    private int nodeIdCounter = 0;  
      
    public NetworkXWriter(String outputDir, String jobId) {  
        this.outputDir = outputDir;  
        this.jobId = jobId;  
          
        try {  
            Files.createDirectories(Paths.get(outputDir));  
        } catch (IOException e) {  
            throw new RuntimeException("Failed to create output directory", e);  
        }  
    }  
      
    @Override  
    public void writeNodes(List<Record> records) {  
        for (Record record : records) {  
            Vertex vertex = (Vertex) record.element();  
            String label = vertex.label();  
            String originalId = preprocessId(vertex.id().toString());  
              
            int nodeId = getOrCreateNodeId(originalId);  
              
            Map<String, Object> nodeData = new HashMap<>();  
            nodeData.put("id", nodeId);  
            nodeData.put("original_id", originalId);  
            nodeData.put("label", label.toLowerCase());  
              
            Map<String, Object> properties = vertex.properties();  
            if (properties != null) {  
                for (Map.Entry<String, Object> prop : properties.entrySet()) {  
                    if (!prop.getKey().equals("id")) {  
                        nodeData.put(prop.getKey(), prop.getValue());  
                    }  
                }  
            }  
              
            nodes.add(nodeData);  
            nodeCounters.merge(label, 1, Integer::sum);  
        }  
    }  
      
    @Override  
    public void writeEdges(List<Record> records) {  
        for (Record record : records) {  
            Edge edge = (Edge) record.element();  
            String label = edge.label().toLowerCase();  
            String sourceId = preprocessId(edge.sourceId().toString());  
            String targetId = preprocessId(edge.targetId().toString());  
              
            Integer sourceNodeId = nodeMapping.get(sourceId);  
            Integer targetNodeId = nodeMapping.get(targetId);  
              
            if (sourceNodeId == null || targetNodeId == null) {  
                System.err.println("Warning: Skipping edge - node not found. Source: " +   
                    sourceId + ", Target: " + targetId);  
                continue;  
            }  
              
            Map<String, Object> edgeData = new HashMap<>();  
            edgeData.put("source", sourceNodeId);  
            edgeData.put("target", targetNodeId);  
            edgeData.put("type", label);  
            edgeData.put("source_label", edge.sourceLabel());  
            edgeData.put("target_label", edge.targetLabel());  
              
            Map<String, Object> properties = edge.properties();  
            if (properties != null) {  
                for (Map.Entry<String, Object> prop : properties.entrySet()) {  
                    if (!prop.getKey().equals("id")) {  
                        edgeData.put(prop.getKey(), prop.getValue());  
                    }  
                }  
            }  
              
            edges.add(edgeData);  
            String edgeKey = label + "|" + edge.sourceLabel() + "|" + edge.targetLabel();  
            edgeCounters.merge(edgeKey, 1, Integer::sum);  
        }  
    }  
      
    public void writeGraph() throws IOException {  
        ObjectMapper mapper = new ObjectMapper();  
        ObjectNode graphData = mapper.createObjectNode();  
          
        graphData.put("directed", true);  
        graphData.put("multigraph", false);  
          
        ArrayNode nodesArray = mapper.createArrayNode();  
        for (Map<String, Object> node : nodes) {  
            nodesArray.add(mapper.valueToTree(node));  
        }  
        graphData.set("nodes", nodesArray);  
          
        ArrayNode edgesArray = mapper.createArrayNode();  
        for (Map<String, Object> edge : edges) {  
            edgesArray.add(mapper.valueToTree(edge));  
        }  
        graphData.set("links", edgesArray);  
          
        // Write temporary JSON file  
        String jsonPath = outputDir + "/networkx_graph_temp.json";  
        mapper.writerWithDefaultPrettyPrinter().writeValue(new java.io.File(jsonPath), graphData);  
          
        // Write metadata  
        ObjectNode metadata = mapper.createObjectNode();  
        metadata.put("node_count", nodes.size());  
        metadata.put("edge_count", edges.size());  
        metadata.set("node_counters", mapper.valueToTree(nodeCounters));  
        metadata.set("edge_counters", mapper.valueToTree(edgeCounters));  
          
        String metadataPath = outputDir + "/networkx_metadata.json";  
        mapper.writerWithDefaultPrettyPrinter().writeValue(new java.io.File(metadataPath), metadata);  
          
        // Convert JSON to pickle using Python  
        convertJsonToPickle(jsonPath, outputDir + "/networkx_graph.pkl");  
          
        // Delete temporary JSON file  
        Files.deleteIfExists(Paths.get(jsonPath));  
          
        System.out.println("NetworkX graph written to: " + outputDir + "/networkx_graph.pkl");  
        System.out.println("Nodes: " + nodes.size() + ", Edges: " + edges.size());  
    }  
      
    private void convertJsonToPickle(String jsonPath, String pklPath) throws IOException {  
        // Create inline Python script  
        String pythonScript = String.format(  
            "import json\n" +  
            "import pickle\n" +  
            "import networkx as nx\n" +  
            "\n" +  
            "with open('%s', 'r') as f:\n" +  
            "    data = json.load(f)\n" +  
            "\n" +  
            "G = nx.DiGraph() if data.get('directed', True) else nx.Graph()\n" +  
            "\n" +  
            "for node in data['nodes']:\n" +  
            "    node_id = node.pop('id')\n" +  
            "    G.add_node(node_id, **node)\n" +  
            "\n" +  
            "for edge in data['links']:\n" +  
            "    source = edge.pop('source')\n" +  
            "    target = edge.pop('target')\n" +  
            "    G.add_edge(source, target, **edge)\n" +  
            "\n" +  
            "with open('%s', 'wb') as f:\n" +  
            "    pickle.dump(G, f, protocol=4)\n" +  
            "\n" +  
            "print(f'Converted to pickle: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')\n",  
            jsonPath.replace("\\", "\\\\"),  
            pklPath.replace("\\", "\\\\")  
        );  
          
        // Execute Python script  
        ProcessBuilder pb = new ProcessBuilder("python3", "-c", pythonScript);  
        pb.redirectErrorStream(true);  
        Process process = pb.start();  
          
        // Read output  
        BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));  
        String line;  
        while ((line = reader.readLine()) != null) {  
            System.out.println(line);  
        }  
          
        try {  
            int exitCode = process.waitFor();  
            if (exitCode != 0) {  
                throw new IOException("Python conversion failed with exit code: " + exitCode);  
            }  
        } catch (InterruptedException e) {  
            Thread.currentThread().interrupt();  
            throw new IOException("Python conversion interrupted", e);  
        }  
    }  
      
    private String preprocessId(String id) {  
        String processed = id.toLowerCase().trim();  
        if (processed.contains(":")) {  
            processed = processed.split(":", 2)[1];  
        }  
        return processed.replace(" ", "_");  
    }  
      
    private synchronized int getOrCreateNodeId(String originalId) {  
        return nodeMapping.computeIfAbsent(originalId, k -> nodeIdCounter++);  
    }  
}