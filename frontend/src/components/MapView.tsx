import { GoogleMap, Marker, Polyline } from "@react-google-maps/api";
import React from "react";
import { useEffect, useRef } from "react";

type Props = {
  center: google.maps.LatLngLiteral;
  start?: google.maps.LatLngLiteral | null;
  end?: google.maps.LatLngLiteral | null;
  route?: google.maps.LatLngLiteral[] | null;
  onMapClick?: (ll: google.maps.LatLngLiteral) => void;
};

export default function MapView({ center, start, end, route, onMapClick }: Props) {
  const mapRef = useRef<google.maps.Map | null>(null);

  function onLoad(map: google.maps.Map) { mapRef.current = map; }

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Fit to route if present; else fit to start/end if both; else center/default zoom
    if (route && route.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      route.forEach(p => bounds.extend(p));
      map.fitBounds(bounds, 60); // padding
    } else if (start && end) {
      const b = new google.maps.LatLngBounds();
      b.extend(start); b.extend(end);
      map.fitBounds(b, 80);
    } else if (start) {
      map.setCenter(start); map.setZoom(14);
    } else if (end) {
      map.setCenter(end); map.setZoom(14);
    } else {
      map.setCenter(center); map.setZoom(8);
    }
  }, [route, start, end, center]);

  return (
    <GoogleMap
      onLoad={onLoad}
      mapContainerStyle={{ width: "100%", height: "100%" }}
      center={center}
      zoom={8}
      options={{ streetViewControl: true, mapTypeControl: false }}
      onClick={(e)=> {
        const lat = e.latLng?.lat(); const lng = e.latLng?.lng();
        if (lat && lng && onMapClick) onMapClick({ lat, lng });
      }}
    >
      {start && <Marker position={start} title="Start" />}
      {end && <Marker position={end} title="End" />}
      {route && route.length>0 && (
        <Polyline path={route} options={{ strokeOpacity: 1, strokeWeight: 6, strokeColor: "#4f8cff" }}/>
      )}
    </GoogleMap>
  );
}
