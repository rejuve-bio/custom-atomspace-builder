package org.apache.hugegraph.loader.writer;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.apache.hugegraph.loader.builder.Record;
import org.apache.hugegraph.structure.graph.Edge;
import org.apache.hugegraph.structure.graph.Vertex;

public class MeTTaWriter {
    
    private final String OUTPUT_DIR;
    private static final ConcurrentHashMap<String, Object> FILE_LOCKS = new ConcurrentHashMap<>();
    
    public MeTTaWriter(String outputDir) {
        this.OUTPUT_DIR = outputDir;
        // Create output directory if it doesn't exist
        try {
            Files.createDirectories(Paths.get(OUTPUT_DIR));
        } catch (IOException e) {
            throw new RuntimeException("Failed to create output directory", e);
        }
    }
    
    /**
     * Write a list of vertices to MeTTa files, one file per label
     */
    public void writeNodes(List<Record> records) {
        Map<String, List<Vertex>> verticesByLabel = groupVerticesByLabel(records);
        
        for (Map.Entry<String, List<Vertex>> entry : verticesByLabel.entrySet()) {
            String label = entry.getKey();
            List<Vertex> vertices = entry.getValue();
            
            String filePath = OUTPUT_DIR + "/" + label + ".metta";
            writeToFileWithLock(filePath, vertices, true);
        }
    }
    
    /**
     * Write a single vertex to MeTTa format
     */
    public String writeNode(Vertex vertex) {
        String id = vertex.id() == null ? "null" : vertex.id().toString();
        String label = vertex.label();
        Map<String, Object> properties = vertex.properties();
        
        StringBuilder result = new StringBuilder();
        result.append("(").append(label).append(" ").append(id).append(")");
        
        // Add properties
        for (Map.Entry<String, Object> prop : properties.entrySet()) {
            String key = prop.getKey();
            Object value = prop.getValue();
            
            if (value != null && !value.toString().isEmpty()) {
                result.append("\n(").append(key).append(" (").append(label).append(" ").append(id).append(") ");
                
                // Handle different property types
                if (value instanceof List) {
                    result.append("(");
                    List<?> list = (List<?>) value;
                    for (int i = 0; i < list.size(); i++) {
                        result.append(checkProperty(list.get(i).toString()));
                        if (i < list.size() - 1) {
                            result.append(" ");
                        }
                    }
                    result.append(")");
                } else {
                    result.append(checkProperty(value.toString()));
                }
                
                result.append(")");
            }
        }
        
        return result.toString();
    }
    
    /**
     * Write a list of edges to MeTTa files, one file per label
     */
    public void writeEdges(List<Record> records) {
        Map<String, List<Edge>> edgesByLabel = groupEdgesByLabel(records);
        
        for (Map.Entry<String, List<Edge>> entry : edgesByLabel.entrySet()) {
            String label = entry.getKey();
            List<Edge> edges = entry.getValue();
            
            String filePath = OUTPUT_DIR + "/" + label + ".metta";
            writeToFileWithLock(filePath, edges, false);
        }
    }
    
    /**
     * Write a single edge to MeTTa format
     */
    public String writeEdge(Edge edge) {
        String sourceId = edge.sourceId() == null ? "null" : edge.sourceId().toString();
        String targetId = edge.targetId() == null ? "null" : edge.targetId().toString();
        String sourceLabel = edge.sourceLabel();
        String targetLabel = edge.targetLabel();
        String label = edge.label();
        Map<String, Object> properties = edge.properties();
        
        StringBuilder result = new StringBuilder();
        result.append("(").append(label).append(" (").append(sourceLabel).append(" ").append(sourceId).append(") ")
              .append("(").append(targetLabel).append(" ").append(targetId).append("))");
        
        // Add properties
        for (Map.Entry<String, Object> prop : properties.entrySet()) {
            String key = prop.getKey();
            Object value = prop.getValue();
            
            if (value != null && !value.toString().isEmpty()) {
                result.append("\n(").append(key).append(" (").append(label)
                      .append(" (").append(sourceLabel).append(" ").append(sourceId).append(") ")
                      .append("(").append(targetLabel).append(" ").append(targetId).append(")) ");
                
                // Handle different property types
                if (value instanceof List) {
                    result.append("(");
                    List<?> list = (List<?>) value;
                    for (int i = 0; i < list.size(); i++) {
                        result.append(checkProperty(list.get(i).toString()));
                        if (i < list.size() - 1) {
                            result.append(" ");
                        }
                    }
                    result.append(")");
                } else {
                    result.append(checkProperty(value.toString()));
                }
                
                result.append(")");
            }
        }
        
        return result.toString();
    }
    
    /**
     * Write elements to file with proper locking to prevent concurrent access issues
     */
    private <T> void writeToFileWithLock(String filePath, List<T> elements, boolean isVertex) {
        // Get or create a lock object for this file
        Object fileLock = FILE_LOCKS.computeIfAbsent(filePath, k -> new Object());
        
        synchronized (fileLock) {
            try (RandomAccessFile file = new RandomAccessFile(filePath, "rw");
                 FileChannel channel = file.getChannel();
                 FileLock lock = channel.lock()) {
                
                // Move to the end of the file
                file.seek(file.length());
                
                // Write the content
                StringBuilder content = new StringBuilder();
                for (T element : elements) {
                    if (isVertex) {
                        content.append(writeNode((Vertex) element)).append("\n");
                    } else {
                        content.append(writeEdge((Edge) element)).append("\n");
                    }
                }
                content.append("\n");
                
                // Write the content to the file
                file.write(content.toString().getBytes());
                
                // Force changes to be written to the disk
                channel.force(true);
            } catch (IOException e) {
                throw new RuntimeException("Failed to write to file: " + filePath, e);
            }
        }
    }
    
    /**
     * Helper method to escape special characters in property values
     */
    private String checkProperty(String prop) {
        if (prop == null) {
            return "null";
        }
        
        if (prop.contains(" ")) {
            prop = prop.replace(" ", "_");
        }
        
        // Escape special characters
        String[] specialChars = {"(", ")"};
        String escapeChar = "\\";
        
        for (String special : specialChars) {
            prop = prop.replace(special, escapeChar + special);
        }
        
        return prop;
    }
    
    /**
     * Group vertices by their label
     */
    private Map<String, List<Vertex>> groupVerticesByLabel(List<Record> records) {
        Map<String, List<Vertex>> result = new java.util.HashMap<>();
        
        for (Record record : records) {
            Vertex vertex = (Vertex) record.element();
            String label = vertex.label();
            
            if (!result.containsKey(label)) {
                result.put(label, new ArrayList<>());
            }
            
            result.get(label).add(vertex);
        }
        
        return result;
    }
    
    /**
     * Group edges by their label
     */
    private Map<String, List<Edge>> groupEdgesByLabel(List<Record> records) {
        Map<String, List<Edge>> result = new java.util.HashMap<>();
        
        for (Record record : records) {
            Edge edge = (Edge) record.element();
            String label = edge.label();
            
            if (!result.containsKey(label)) {
                result.put(label, new ArrayList<>());
            }
            
            result.get(label).add(edge);
        }
        
        return result;
    }
}