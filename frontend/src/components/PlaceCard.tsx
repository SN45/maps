type Props = {
  title: string;
  place?: google.maps.places.PlaceResult | null;
};

function photoUrl(p?: google.maps.places.PlaceResult | null) {
  const photo = p?.photos?.[0];
  return photo?.getUrl({ maxWidth: 400, maxHeight: 300 });
}

export default function PlaceCard({ title, place }: Props) {
  if (!place) return null;
  const url = photoUrl(place);
  return (
    <div style={{
      marginTop: 10, padding: 10, border: "1px solid #eee",
      borderRadius: 10
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 13, color: "#444", marginBottom: 8 }}>
        {place.name || "Selected place"}
      </div>
      {place.formatted_address && (
        <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>
          {place.formatted_address}
        </div>
      )}
      {url && (
        <img
          src={url}
          style={{ width: "100%", borderRadius: 8, display: "block" }}
          alt={place.name || "Place photo"}
        />
      )}
    </div>
  );
}
