"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Circle,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useDrivers } from "@/lib/realtime";
import { selectLoad, useUI } from "@/lib/store";
import { INITIAL_CENTER, INITIAL_ZOOM } from "@/lib/constants";
import { cn } from "@/lib/utils";

function statusColor(status: string, loadStatus: string | null) {
  if (loadStatus === "exception") return "#ef4444";
  if (status === "driving") return "#3b82f6";
  if (loadStatus === "at_pickup" || loadStatus === "at_delivery") return "#22c55e";
  if (status === "off_duty" || status === "sleeper") return "#9ca3af";
  return "#3b82f6";
}

function makeTruckIcon(color: string, isException: boolean, isSelected: boolean) {
  const ring = isException
    ? '<span class="absolute inset-0 -m-1 rounded-full" style="background:rgba(239,68,68,0.4);animation:pingRing 1.6s cubic-bezier(0,0,0.2,1) infinite"></span>'
    : "";
  const size = isSelected ? 14 : 12;
  return L.divIcon({
    className: "relay-truck-marker",
    iconSize: [size + 8, size + 8],
    iconAnchor: [(size + 8) / 2, (size + 8) / 2],
    html: `<div class="relative cursor-pointer" style="width:${size + 8}px;height:${size + 8}px;display:flex;align-items:center;justify-content:center;">${ring}<span class="relative block rounded-full" style="width:${size}px;height:${size}px;background:${color};box-shadow:0 0 0 2px #fff;"></span></div>`,
  });
}

function FlyToSelected() {
  const ui = useUI();
  const drivers = useDrivers();
  const map = useMap();

  useEffect(() => {
    if (!ui.selectedLoadId) return;
    const row = drivers.find(
      (d) => d.active_load?.load_id === ui.selectedLoadId,
    );
    if (!row?.current_lat || !row?.current_lng) return;
    map.flyTo([row.current_lat, row.current_lng], 7.5, { duration: 1.2 });
  }, [ui.selectedLoadId, drivers, map]);

  return null;
}

/** Keep Leaflet's internal size in sync with the container. The right panel
 *  animates width changes and Leaflet doesn't observe mutation on its parent
 *  by default. ResizeObserver + invalidateSize keeps tiles filled. */
function InvalidateOnResize({ container }: { container: HTMLDivElement | null }) {
  const map = useMap();
  useEffect(() => {
    if (!container) return;
    const ro = new ResizeObserver(() => {
      // Defer one frame so the browser has committed the new size.
      requestAnimationFrame(() => map.invalidateSize({ animate: false }));
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, [container, map]);
  return null;
}

export default function FleetMap() {
  const drivers = useDrivers();
  const ui = useUI();
  const [wrapEl, setWrapEl] = useState<HTMLDivElement | null>(null);

  const driving = drivers.filter((d) => d.status === "driving").length;
  const atStop = drivers.filter(
    (d) =>
      d.active_load &&
      (d.active_load.status === "at_pickup" ||
        d.active_load.status === "at_delivery"),
  ).length;
  const exceptions = drivers.filter(
    (d) => d.active_load?.status === "exception",
  ).length;

  const routes = useMemo(
    () =>
      drivers
        .filter(
          (d) =>
            d.active_load &&
            d.active_load.status !== "delivered" &&
            d.current_lat != null &&
            d.current_lng != null,
        )
        .map((d) => ({
          load_id: d.active_load!.load_id,
          is_exception: d.active_load!.status === "exception",
          positions: [
            [d.current_lat!, d.current_lng!] as [number, number],
            [d.active_load!.delivery.lat, d.active_load!.delivery.lng] as [number, number],
          ],
        })),
    [drivers],
  );

  const stops = useMemo(() => {
    const arr: Array<{
      key: string;
      pos: [number, number];
      isException: boolean;
    }> = [];
    for (const d of drivers) {
      if (!d.active_load) continue;
      arr.push({
        key: `${d.driver_id}-pickup`,
        pos: [d.active_load.pickup.lat, d.active_load.pickup.lng],
        isException: false,
      });
      arr.push({
        key: `${d.driver_id}-delivery`,
        pos: [d.active_load.delivery.lat, d.active_load.delivery.lng],
        isException: d.active_load.status === "exception",
      });
    }
    return arr;
  }, [drivers]);

  return (
    <div ref={setWrapEl} className="relative h-full w-full">
      <MapContainer
        center={INITIAL_CENTER}
        zoom={INITIAL_ZOOM}
        scrollWheelZoom
        zoomControl={false}
        className="h-full w-full"
      >
        <InvalidateOnResize container={wrapEl} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          subdomains={["a", "b", "c", "d"]}
          maxZoom={19}
        />
        <FlyToSelected />

        {routes.map((r) => (
          <Polyline
            key={r.load_id}
            positions={r.positions}
            pathOptions={{
              color: r.is_exception ? "#ef4444" : "#3b82f6",
              opacity: r.is_exception ? 0.55 : 0.45,
              weight: 2,
              dashArray: "4 6",
            }}
          />
        ))}

        {stops.map((s) => (
          <Circle
            key={s.key}
            center={s.pos}
            radius={8000}
            pathOptions={{
              color: s.isException ? "rgba(239,68,68,0.55)" : "rgba(59,130,246,0.35)",
              fillColor: s.isException ? "rgba(239,68,68,0.15)" : "rgba(59,130,246,0.1)",
              fillOpacity: 1,
              weight: 1,
            }}
          />
        ))}

        {drivers.map((d) => {
          if (d.current_lat == null || d.current_lng == null) return null;
          const loadStatus = d.active_load?.status ?? null;
          const color = statusColor(d.status, loadStatus);
          const isException = loadStatus === "exception";
          const isSelected = d.active_load?.load_id === ui.selectedLoadId;
          return (
            <Marker
              key={d.driver_id}
              position={[d.current_lat, d.current_lng]}
              icon={makeTruckIcon(color, isException, isSelected)}
              title={`${d.name} · #${d.truck_number}`}
              eventHandlers={{
                click: () => {
                  if (d.active_load) selectLoad(d.active_load.load_id, d.driver_id);
                },
              }}
            />
          );
        })}
      </MapContainer>

      <div className="pointer-events-none absolute left-4 top-4 z-[20] rounded-lg border border-ink-100 bg-white/90 px-3 py-2 text-[11px] shadow-soft backdrop-blur">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-400">
          Fleet status
        </div>
        <div className="flex items-center gap-3 text-ink-600">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-accent-500" />
            {driving} driving
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            {atStop} at stop
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            {exceptions} exception
          </span>
        </div>
      </div>

      <style jsx global>{`
        @keyframes pingRing {
          0% {
            transform: scale(1);
            opacity: 0.8;
          }
          100% {
            transform: scale(3);
            opacity: 0;
          }
        }
        .leaflet-container {
          background: #f8fafc;
          font-family: inherit;
        }
      `}</style>
    </div>
  );
}
