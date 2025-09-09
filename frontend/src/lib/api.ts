import axios from "axios";
export const api = axios.create({ baseURL: "http://localhost:8000" });

export async function getRoute(params: {
  start: google.maps.LatLngLiteral;
  end: google.maps.LatLngLiteral;
}) {
  const { start, end } = params;
  const res = await api.get("/route", {
    params: {
      start_lat: start.lat, start_lng: start.lng,
      end_lat: end.lat,     end_lng: end.lng
    }
  });
  return res.data as {
    polyline: google.maps.LatLngLiteral[];
    meters: number | null;
    seconds: number | null;
    error?: string;
  };
}
