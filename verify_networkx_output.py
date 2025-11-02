
import pickle  
import networkx as nx  
from pathlib import Path  
import sys  
  
def verify_networkx_pickle(pkl_path):  
    """  
    Verify the contents of a NetworkX pickle file  
      
    Args:  
        pkl_path: Path to the .pkl file  
    """  
    print(f"=== Verifying NetworkX Pickle File ===")  
    print(f"File: {pkl_path}\n")  
      
    # Check if file exists  
    if not Path(pkl_path).exists():  
        print(f"❌ Error: File not found at {pkl_path}")  
        return False  
      
    # Load the pickle file  
    try:  
        with open(pkl_path, 'rb') as f:  
            G = pickle.load(f)  
        print("✅ Successfully loaded pickle file")  
    except Exception as e:  
        print(f"❌ Error loading pickle file: {e}")  
        return False  
      
    # Verify it's a NetworkX graph  
    if not isinstance(G, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):  
        print(f"❌ Error: Loaded object is not a NetworkX graph (type: {type(G)})")  
        return False  
    print(f"✅ Object is a valid NetworkX graph (type: {type(G).__name__})")  
      
    # Check graph properties  
    print(f"\n--- Graph Properties ---")  
    print(f"Graph type: {'Directed' if G.is_directed() else 'Undirected'}")  
    print(f"Number of nodes: {G.number_of_nodes()}")  
    print(f"Number of edges: {G.number_of_edges()}")  
      
    # Verify expected node count  
    expected_nodes = 3  # Alice, Bob, Charlie from test_data.csv  
    if G.number_of_nodes() != expected_nodes:  
        print(f"⚠️  Warning: Expected {expected_nodes} nodes, found {G.number_of_nodes()}")  
    else:  
        print(f"✅ Node count matches expected ({expected_nodes})")  
      
    # Display node information  
    print(f"\n--- Node Information ---")  
    for node_id, node_data in G.nodes(data=True):  
        print(f"\nNode ID: {node_id}")  
        print(f"  Properties: {node_data}")  
          
        # Verify expected properties  
        expected_props = ['name', 'age', 'city']  
        missing_props = [prop for prop in expected_props if prop not in node_data]  
        if missing_props:  
            print(f"  ⚠️  Missing properties: {missing_props}")  
        else:  
            print(f"  ✅ All expected properties present")  
      
    # Display edge information (if any)  
    if G.number_of_edges() > 0:  
        print(f"\n--- Edge Information ---")  
        for source, target, edge_data in G.edges(data=True):  
            print(f"\nEdge: {source} -> {target}")  
            print(f"  Properties: {edge_data}")  
    else:  
        print(f"\n--- No edges in graph ---")  
      
    # Verify graph structure  
    print(f"\n--- Graph Structure Verification ---")  
      
    # Check if graph is connected (for undirected) or weakly connected (for directed)  
    if G.is_directed():  
        is_connected = nx.is_weakly_connected(G)  
        connectivity_type = "weakly connected"  
    else:  
        is_connected = nx.is_connected(G)  
        connectivity_type = "connected"  
      
    print(f"Graph is {connectivity_type}: {is_connected}")  
      
    # Summary  
    print(f"\n=== Verification Summary ===")  
    print(f"✅ Pickle file is valid")  
    print(f"✅ Contains a NetworkX {type(G).__name__}")  
    print(f"✅ Has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")  
      
    return True  
  
def main():  
    """Main function to run verification"""  
    if len(sys.argv) < 2:  
        print("Usage: python verify_networkx_output.py <path_to_pkl_file>")  
        print("\nExample:")  
        print("  python verify_networkx_output.py output/fdd354e8-d1ad-4761-89cf-caeb11acb68a/networkx_graph.pkl")  
        sys.exit(1)  
      
    pkl_path = sys.argv[1]  
    success = verify_networkx_pickle(pkl_path)  
      
    if success:  
        print("\n✅ Verification completed successfully!")  
        sys.exit(0)  
    else:  
        print("\n❌ Verification failed!")  
        sys.exit(1)  
  
if __name__ == "__main__":  
    main()