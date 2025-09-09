// frontend/src/components/PlaceInput.tsx
import React from "react";
import { useEffect, useRef, useState } from "react";

type Props = {
  label: string;
  onSelect: (res: { latlng: google.maps.LatLngLiteral; place?: google.maps.places.PlaceResult }) => void;
  onBeginEdit?: () => void; // <-- new
};

export default function PlaceInput({ label, onSelect, onBeginEdit }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const acRef = useRef<google.maps.places.Autocomplete | null>(null);
  const [value, setValue] = useState("");

  useEffect(() => {
    if (!inputRef.current || acRef.current) return;
    const ac = new google.maps.places.Autocomplete(inputRef.current!, {
      fields: ["geometry", "formatted_address", "name"],
      types: ["geocode"],
    });
    ac.addListener("place_changed", () => {
      const place = ac.getPlace();
      const loc = place?.geometry?.location;
      if (!loc) return;
      const latlng = { lat: loc.lat(), lng: loc.lng() };
      // set the input to a nice label
      setValue(place.formatted_address || place.name || `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`);
      onSelect({ latlng, place });
    });
    acRef.current = ac;
  }, [onSelect]);

  return (
    <div style={{ display: "grid", gap: 6 }}>
      <label style={{ fontSize: 12, color: "#9bb0d1" }}>{label}</label>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => {
          if (onBeginEdit) onBeginEdit();
          setValue(e.target.value);
        }}
        onFocus={() => {
          if (onBeginEdit) onBeginEdit();
        }}
        placeholder={`Search ${label}...`}
        style={{
          width: "100%",
          padding: "10px 12px",
          borderRadius: 10,
          border: "1px solid #22314f",
          background: "#0f1730",
          color: "#e7eefc",
          outline: "none",
        }}
      />
    </div>
  );
}
