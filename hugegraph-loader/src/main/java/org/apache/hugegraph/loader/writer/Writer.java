package org.apache.hugegraph.loader.writer;
import org.apache.hugegraph.loader.builder.Record;

import java.util.List;

public interface Writer {
    void writeNodes(List<Record> records);
    void writeEdges(List<Record> records);
}