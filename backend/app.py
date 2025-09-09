# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os, pickle, math, sys, traceback, requests
import networkx as nx
import osmnx as ox
from shapely.geometry import box as shapely_box

# ---------- FastAPI ----------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Speed & cache settings ----------
ox.settings.use_cache = True          # cache Overpass responses
ox.settings.log_console = False
ox.settings.requests_timeout = 180
ox.settings.overpass_rate_limit = True

FORCE_REBUILD = False                 # leave False so tiles load from disk once built
MIN_NODES = 400                       # "tiny graph" detector (for rebuild via polygon)

BASE_DIR = os.path.dirname(__file__)
TILES_DIR = os.path.join(BASE_DIR, "data", "graphs", "tiles")
os.makedirs(TILES_DIR, exist_ok=True)

def log(*a): print("[Flash_Direx]", *a, file=sys.stdout, flush=True)

# ==========================
#    GEOMETRY HELPERS
# ==========================
def haversine(a, b):
    (lat1, lon1), (lat2, lon2) = a, b
    R = 6371000
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    h = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

def deg_buffer_for_km(lat, km):
    dlat = km / 110.574
    dlon = km / (111.320 * max(0.1, math.cos(math.radians(lat))))
    return dlat, dlon

def compute_buffer_km(start_lat, start_lng, end_lat, end_lng):
    # smaller default corridor -> faster builds; you can override with &buffer_km= on the URL
    dist_km = haversine((start_lat,start_lng),(end_lat,end_lng))/1000.0
    return max(8.0, min(60.0, dist_km * 0.05))

# ==========================
#         OSRM (fast)
# ==========================
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")

def route_via_osrm(start_lat, start_lng, end_lat, end_lng, timeout=8.0):
    """Use public OSRM demo (fast). No key needed."""
    url = f"{OSRM_URL}/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {"overview": "full", "geometries": "geojson"}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    route = data["routes"][0]
    coords = route["geometry"]["coordinates"]  # [lon, lat] pairs
    poly = [{"lat": float(lat), "lng": float(lon)} for lon, lat in coords]
    return {"polyline": poly, "meters": float(route["distance"]), "seconds": float(route["duration"])}

# ==========================
#      OSMNX (fallback)
# ==========================
GRAPH_CACHE = {}
def tile_key(north, south, east, west):
    r = lambda x: f"{x:.3f}"
    return f"{r(north)}_{r(south)}_{r(east)}_{r(west)}"

def build_graph_from_bbox_compat(north: float, south: float, east: float, west: float):
    try:
        if hasattr(ox, "graph") and hasattr(ox.graph, "graph_from_bbox"):
            return ox.graph.graph_from_bbox(north=north, south=south, east=east, west=west, network_type="drive")
    except Exception:
        pass
    try:
        if hasattr(ox, "graph_from_bbox"):
            return ox.graph_from_bbox(bbox=(north, south, east, west), network_type="drive")
    except Exception:
        pass
    try:
        if hasattr(ox, "graph_from_bbox"):
            return ox.graph_from_bbox(north, south, east, west, network_type="drive")
    except Exception:
        pass
    poly = shapely_box(west, south, east, north)
    try:
        if hasattr(ox, "graph") and hasattr(ox.graph, "graph_from_polygon"):
            return ox.graph.graph_from_polygon(poly, network_type="drive")
    except Exception:
        pass
    return ox.graph_from_polygon(poly, network_type="drive")

def prune_to_giant(G):
    try:
        UG = G.to_undirected(as_view=False)
        comps = list(nx.connected_components(UG))
        if comps:
            giant = max(comps, key=len)
            if len(giant) < UG.number_of_nodes():
                log(f"pruning to largest component: {len(giant)} / {UG.number_of_nodes()} nodes")
            return G.subgraph(giant).copy()
    except Exception as e:
        log("component prune failed:", repr(e))
    return G

def load_or_build_bbox(north, south, east, west):
    key = tile_key(north, south, east, west)
    fp = os.path.join(TILES_DIR, f"{key}.pkl")

    if (not FORCE_REBUILD) and key in GRAPH_CACHE:
        return GRAPH_CACHE[key]
    if (not FORCE_REBUILD) and os.path.exists(fp):
        with open(fp, "rb") as f: G = pickle.load(f)
        GRAPH_CACHE[key] = G
        log("loaded tile", key, f"({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
        return G

    log("building tile", key)
    G = build_graph_from_bbox_compat(north, south, east, west)
    G = ox.distance.add_edge_lengths(G)
    try:
        if hasattr(ox, "speed"):
            G = ox.speed.add_edge_speeds(G)
            G = ox.speed.add_edge_travel_times(G)
        else:
            G = ox.add_edge_speeds(G)
            G = ox.add_edge_travel_times(G)
    except Exception as e:
        log("speed/tt add failed:", repr(e))

    # If fetch looks suspiciously tiny, rebuild via polygon
    if G.number_of_nodes() < MIN_NODES:
        log("bbox looks tiny → trying polygon fallback")
        poly = shapely_box(west, south, east, north)
        try:
            if hasattr(ox, "graph") and hasattr(ox.graph, "graph_from_polygon"):
                G2 = ox.graph.graph_from_polygon(poly, network_type="drive")
            else:
                G2 = ox.graph_from_polygon(poly, network_type="drive")
            G2 = ox.distance.add_edge_lengths(G2)
            try:
                if hasattr(ox, "speed"):
                    G2 = ox.speed.add_edge_speeds(G2)
                    G2 = ox.speed.add_edge_travel_times(G2)
                else:
                    G2 = ox.add_edge_speeds(G2)
                    G2 = ox.add_edge_travel_times(G2)
            except Exception as e:
                log("speed/tt add failed (poly):", repr(e))
            if G2.number_of_nodes() > G.number_of_nodes():
                G = G2
        except Exception as e:
            log("polygon fallback failed:", repr(e))

    G = prune_to_giant(G)
    with open(fp, "wb") as f: pickle.dump(G, f)
    GRAPH_CACHE[key] = G
    log("saved tile", key, f"({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
    return G

def build_corridor(start_lat, start_lng, end_lat, end_lng, buffer_km):
    mid_lat = (start_lat + end_lat) / 2.0
    dlat, dlon = deg_buffer_for_km(mid_lat, buffer_km)
    north = max(start_lat, end_lat) + dlat
    south = min(start_lat, end_lat) - dlat
    east  = max(start_lng, end_lng) + dlon
    west  = min(start_lng, end_lng) - dlon
    return load_or_build_bbox(north, south, east, west)

def nearest_node_fast(G, lat, lng):
    try:
        nid = ox.distance.nearest_nodes(G, X=lng, Y=lat)
        d = haversine((lat, lng), (G.nodes[nid]["y"], G.nodes[nid]["x"]))
        return nid, d
    except Exception:
        # manual fallback
        best = None; best_d = 1e20
        for n, data in G.nodes(data=True):
            dist = haversine((lat, lng), (data["y"], data["x"]))
            if dist < best_d: best, best_d = n, dist
        return best, best_d

def best_edge_key(G, u, v):
    # choose the fastest edge u->v (or any)
    if not G.has_edge(u, v): return None
    best_k = None; best = 1e20
    for k, ed in G[u][v].items():
        t = ed.get("travel_time", None)
        if t is None: t = float(ed.get("length", 1e9)/12.5)
        if t < best: best, best_k = t, k
    return best_k

def flatten_coords(geom):
    try:
        if geom.geom_type == "LineString": return list(geom.coords)
        if geom.geom_type == "MultiLineString":
            out=[]; [out.extend(list(ls.coords)) for ls in geom.geoms]; return out
    except Exception:
        pass
    return None

def edge_coords(G, u, v, k):
    ed = G[u][v][k]
    geom = ed.get("geometry")
    if geom is not None:
        coords = flatten_coords(geom)
        if coords: return [{"lat": float(y), "lng": float(x)} for (x, y) in coords]
    return [{"lat": float(G.nodes[u]["y"]), "lng": float(G.nodes[u]["x"])},
            {"lat": float(G.nodes[v]["y"]), "lng": float(G.nodes[v]["x"])}]

def edge_len_m(G, u, v):
    vals = [float(ed.get("length", 0.0)) for _, ed in G[u][v].items() if ed.get("length") is not None]
    if vals: return min(vals)
    return haversine((G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"]))

def polyline_from_path(G, path_nodes, undirected=False):
    meters = 0.0; poly=[]
    for i in range(len(path_nodes)-1):
        u, v = path_nodes[i], path_nodes[i+1]
        if not undirected:
            k = best_edge_key(G, u, v)
            if k is None and G.has_edge(v, u):
                k = best_edge_key(G, v, u)
                seg = edge_coords(G, v, u, k); seg.reverse()
                L = edge_len_m(G, v, u)
            else:
                seg = edge_coords(G, u, v, k)
                L = edge_len_m(G, u, v)
        else:
            if G.has_edge(u, v):
                k = best_edge_key(G, u, v); seg = edge_coords(G, u, v, k); L = edge_len_m(G, u, v)
            elif G.has_edge(v, u):
                k = best_edge_key(G, v, u); seg = edge_coords(G, v, u, k); seg.reverse(); L = edge_len_m(G, v, u)
            else:
                seg = [{"lat": float(G.nodes[u]["y"]), "lng": float(G.nodes[u]["x"])},
                       {"lat": float(G.nodes[v]["y"]), "lng": float(G.nodes[v]["x"])}]
                L = haversine((G.nodes[u]["y"],G.nodes[u]["x"]), (G.nodes[v]["y"],G.nodes[v]["x"]))
        if i>0 and seg: seg = seg[1:]
        poly.extend(seg); meters += L
    return poly, meters

def route_via_osmnx(start_lat, start_lng, end_lat, end_lng, buffer_km):
    G = build_corridor(start_lat, start_lng, end_lat, end_lng, buffer_km)
    s, sd = nearest_node_fast(G, start_lat, start_lng)
    t, td = nearest_node_fast(G, end_lat, end_lng)
    # quick connectivity check
    try:
        UG = ox.utils_graph.get_undirected(G)
    except Exception:
        UG = G.to_undirected(as_view=False)
    if not nx.has_path(UG, s, t):
        return None
    # directed, travel_time
    path = None
    try:
        path = ox.routing.shortest_path(G, s, t, weight="travel_time")
    except Exception:
        try:
            path = ox.shortest_path(G, s, t, weight="travel_time")
        except Exception:
            path = None
    if path and len(path) >= 2:
        poly, meters = polyline_from_path(G, path, undirected=False)
        secs = 0.0
        for u, v in zip(path[:-1], path[1:]):
            if G.has_edge(u, v):
                best = min((ed.get("travel_time", edge_len_m(G,u,v)/12.5) for ed in G[u][v].values()))
            elif G.has_edge(v, u):
                best = min((ed.get("travel_time", edge_len_m(G,v,u)/12.5) for ed in G[v][u].values()))
            else:
                best = edge_len_m(G,u,v)/12.5
            secs += float(best)
        return {"polyline": poly, "meters": meters, "seconds": float(secs)}
    # directed, length
    path = None
    try:
        path = ox.routing.shortest_path(G, s, t, weight="length")
    except Exception:
        try:
            path = ox.shortest_path(G, s, t, weight="length")
        except Exception:
            path = None
    if path and len(path) >= 2:
        poly, meters = polyline_from_path(G, path, undirected=False)
        secs = meters / 12.5
        return {"polyline": poly, "meters": meters, "seconds": float(secs)}
    # undirected safety
    try:
        path = nx.shortest_path(UG, s, t)
    except Exception:
        path = None
    if path and len(path) >= 2:
        poly, meters = polyline_from_path(G, path, undirected=True)
        secs = meters / 12.5
        return {"polyline": poly, "meters": meters, "seconds": float(secs)}
    return None

# ==========================
#          ROUTES
# ==========================
@app.get("/")
def home():
    return {
        "service":"Flash_Direx API",
        "endpoints":["/health","/route"],
        "example":"/route?start_lat=32.781&start_lng=-96.798&end_lat=32.790&end_lng=-96.810"
    }

@app.get("/health")
def health(): return {"ok": True, "osmnx": getattr(ox, "__version__", "unknown"), "osrm": OSRM_URL}

@app.get("/route")
def route(start_lat: float, start_lng: float, end_lat: float, end_lng: float,
          buffer_km: float | None = None, engine: str = "auto"):
    """
    engine: "auto" (OSRM then local), "osrm", or "local"
    buffer_km: optional corridor size for local engine (defaults computed)
    """
    try:
        # 1) OSRM first (super fast)
        if engine in ("auto", "osrm"):
            try:
                osrm_res = route_via_osrm(start_lat, start_lng, end_lat, end_lng, timeout=8.0)
                if osrm_res: return osrm_res
                log("OSRM returned no route; falling back to local OSMnx")
            except Exception as e:
                log("OSRM error:", repr(e))

        # 2) Local OSMnx fallback (fast after first cached build)
        buf = buffer_km if buffer_km is not None else compute_buffer_km(start_lat,start_lng,end_lat,end_lng)
        for mult in (1.0, 1.6, 2.3):
            res = route_via_osmnx(start_lat, start_lng, end_lat, end_lng, buffer_km=min(60.0, buf*mult))
            if res: return res

        return {"polyline": [], "meters": None, "seconds": None, "error": "no_path"}
    except Exception as e:
        log("EXCEPTION:", repr(e))
        traceback.print_exc()
        return {"polyline": [], "meters": None, "seconds": None, "error": "server_error", "detail": str(e)}
