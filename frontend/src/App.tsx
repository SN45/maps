// frontend/src/App.tsx
import { useMemo, useState } from "react";
import { LoadScript } from "@react-google-maps/api";
import MapView from "./components/MapView";
import PlaceInput from "./components/PlaceInput";
import { getRoute } from "./lib/api";
import React from "react";

const M_PER_MI = 1609.344;
const fmtMiles = (m?: number|null) => m==null ? "-" : (m/M_PER_MI).toFixed(2)+" mi";
const fmtEta = (s?: number|null) => {
  if (s==null) return "-";
  const m = Math.round(s/60);
  return m>=60 ? `${Math.floor(m/60)} hr ${m%60} min` : `${m} min`;
};

export default function App() {
  const center = useMemo(() => ({ lat: 31.0, lng: -99.0 }), []);
  const [start, setStart] = useState<google.maps.LatLngLiteral | null>(null);
  const [end, setEnd] = useState<google.maps.LatLngLiteral | null>(null);

  const [route, setRoute] = useState<google.maps.LatLngLiteral[] | null>(null);
  const [meters, setMeters] = useState<number | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);

  function clearRouteState() {
    setRoute(null);
    setMeters(null);
    setSeconds(null);
    setWarning(null);
  }

  function useGPS(setter: (ll: google.maps.LatLngLiteral)=>void) {
    if (!navigator.geolocation) { alert("Geolocation not supported"); return; }
    // clear existing route when changing either endpoint via GPS
    clearRouteState();
    navigator.geolocation.getCurrentPosition(
      pos => setter({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      err => alert("Location error: " + err.message),
      { enableHighAccuracy:true, maximumAge:10000, timeout:10000 }
    );
  }

  async function handleRoute() {
    if (!start || !end) return;
    setLoading(true); setWarning(null);
    try {
      const r = await getRoute({ start, end });
      if (!r || r.meters == null || r.seconds == null || !r.polyline || r.polyline.length < 2) {
        clearRouteState();
        setWarning("No drivable path found in the area. Try closer points or retry.");
        return;
      }
      setRoute(r.polyline);
      setMeters(r.meters);
      setSeconds(r.seconds);
    } catch (e:any) {
      console.error(e);
      clearRouteState();
      setWarning("Routing failed. Check the backend terminal for details.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <LoadScript googleMapsApiKey={import.meta.env.VITE_GOOGLE_MAPS_API_KEY} libraries={["places"]}>
      <div style={{
        display:"grid", gridTemplateColumns:"380px 1fr", height:"100vh",
        background:"linear-gradient(180deg,#0f1630,#0b1020)", color:"#e7eefc"
      }}>
        <aside style={{padding:16, borderRight:"1px solid #22314f", overflowY:"auto"}}>
          <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:10}}>
            <h1 style={{margin:0, fontSize:22, letterSpacing:.3}}>Flash_Direx</h1>
            <span style={{fontSize:11, padding:"2px 6px", border:"1px solid #22314f", borderRadius:999, color:"#9bb0d1"}}>Texas</span>
          </div>

          {/* START input */}
          <div style={{display:"grid", gridTemplateColumns:"1fr 42px", gap:10, marginBottom:8}}>
            <PlaceInput
              label="Start"
              onBeginEdit={clearRouteState}          // <-- clear when editing begins
              onSelect={({latlng})=> { setStart(latlng); }}
            />
            <button title="Use my location" onClick={()=> useGPS(ll=>setStart(ll))}
              style={{borderRadius:10, border:"1px solid #22314f", background:"#0f1730", color:"#e7eefc", cursor:"pointer"}}>📍</button>
          </div>

          {/* END input */}
          <div style={{display:"grid", gridTemplateColumns:"1fr 42px", gap:10, marginBottom:12}}>
            <PlaceInput
              label="End"
              onBeginEdit={clearRouteState}          // <-- clear when editing begins
              onSelect={({latlng})=> { setEnd(latlng); }}
            />
            <button title="Use my location" onClick={()=> useGPS(ll=>setEnd(ll))}
              style={{borderRadius:10, border:"1px solid #22314f", background:"#0f1730", color:"#e7eefc", cursor:"pointer"}}>📍</button>
          </div>

          <div style={{display:"flex", gap:10, alignItems:"center", marginBottom:12}}>
            <button onClick={handleRoute} disabled={!start || !end || loading}
              style={{
                border:"none", borderRadius:10, padding:"10px 14px",
                background: loading ? "#325fb3" : "#4f8cff", color:"white", fontWeight:600, cursor:"pointer",
                boxShadow:"0 6px 20px rgba(79,140,255,.25)", transition:"transform .1s ease"
              }}
              onMouseDown={e=>(e.currentTarget.style.transform="scale(.98)")}
              onMouseUp={e=>(e.currentTarget.style.transform="scale(1)")}>
              {loading? "Routing…" : "Route"}
            </button>
            <button onClick={()=>{
              setStart(null); setEnd(null); clearRouteState();
            }} style={{borderRadius:10, border:"1px solid #22314f", background:"transparent", color:"#9bb0d1", padding:"10px 14px", cursor:"pointer"}}>
              Clear
            </button>
          </div>

          {warning && (
            <div style={{marginBottom:10, color:"#ffb4b4"}}>⚠ {warning}</div>
          )}

          <div style={{border:"1px solid #22314f", borderRadius:14, padding:12, background:"#121a2b"}}>
            <div style={{fontSize:14, color:"#9bb0d1"}}>
              <b style={{color:"#fff"}}>Distance:</b> {fmtMiles(meters)} &nbsp;&nbsp; <b style={{color:"#fff"}}>ETA:</b> {fmtEta(seconds)}
            </div>
          </div>

          <div style={{fontSize:12, color:"#9bb0d1", marginTop:10}}>
            Tip: clicking Start/End clears the previous route so you can set a new one.
          </div>
        </aside>

        <MapView
          center={center}
          start={start}
          end={end}
          route={route || undefined}
          onMapClick={(ll)=>{
            // clicking on map also clears the old route; then set point
            clearRouteState();
            if (!start) setStart(ll); else if (!end) setEnd(ll); else setEnd(ll);
          }}
        />
      </div>
    </LoadScript>
  );
}
