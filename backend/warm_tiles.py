# backend/warm_tiles.py
import pickle, os
import osmnx as ox
from app import build_corridor

# downtown Dallas-ish → Plano corridor example
start_lat, start_lng = 32.781, -96.798
end_lat, end_lng   = 33.000, -96.700
buffer_km = 12  # small, city corridor

print("Building Dallas corridor tile once...")
G = build_corridor(start_lat, start_lng, end_lat, end_lng, buffer_km)
print("Done. Nodes/edges:", G.number_of_nodes(), G.number_of_edges())
