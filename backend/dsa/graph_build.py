import osmnx as ox, pickle, os

def build_and_save_city(city_name: str, place: str):
    G = ox.graph_from_place(place, network_type="drive")
    # lengths (meters)
    G = ox.distance.add_edge_lengths(G)
    # add speed (kph) and travel_time (seconds) if available
    try:
        G = ox.speed.add_edge_speeds(G)          # adds 'speed_kph'
        G = ox.speed.add_edge_travel_times(G)    # adds 'travel_time' (sec)
    except Exception:
        pass

    outdir = os.path.join(os.path.dirname(__file__), "..", "data", "graphs")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{city_name}.pkl"), "wb") as f:
        pickle.dump(G, f)
    print(f"saved {city_name}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

if __name__ == "__main__":
    build_and_save_city("dfw", "DFW, Texas, USA")
