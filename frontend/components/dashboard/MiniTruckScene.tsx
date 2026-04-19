"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Edges } from "@react-three/drei";
import { useRef, type ReactNode } from "react";
import type { Group } from "three";

interface Props {
  /** Tint color of the wireframe — maps to load status. */
  color?: string;
  /** Whether to pulse (exception loads). */
  pulse?: boolean;
}

/** A 3D box that renders as its edge outline only — no face fill,
 *  no face-diagonal triangulation. Uses drei's <Edges /> which wraps
 *  Three's EdgesGeometry so only true edges are stroked. */
function WireBox({
  size,
  position,
  color,
}: {
  size: [number, number, number];
  position: [number, number, number];
  color: string;
}) {
  return (
    <mesh position={position}>
      <boxGeometry args={size} />
      <meshBasicMaterial transparent opacity={0} />
      <Edges color={color} lineWidth={1.5} threshold={1} />
    </mesh>
  );
}

function WireCylinder({
  radius,
  height,
  position,
  color,
  rotation = [Math.PI / 2, 0, 0],
  segments = 18,
}: {
  radius: number;
  height: number;
  position: [number, number, number];
  color: string;
  rotation?: [number, number, number];
  segments?: number;
}) {
  return (
    <mesh position={position} rotation={rotation}>
      <cylinderGeometry args={[radius, radius, height, segments]} />
      <meshBasicMaterial transparent opacity={0} />
      <Edges color={color} lineWidth={1.5} threshold={15} />
    </mesh>
  );
}

function Truck({ color, pulse }: Props) {
  const ref = useRef<Group>(null);
  const lineColor = color ?? "#3b82f6";

  useFrame((_, delta) => {
    if (!ref.current) return;
    ref.current.rotation.y += delta * 0.22;
    if (pulse) {
      const t = performance.now() / 1000;
      ref.current.position.y = -0.05 + Math.sin(t * 2) * 0.02;
    }
  });

  // Dimensions — classic long-nose tractor + 48' box trailer, scaled to fit.
  const TRAILER = { w: 3.4, h: 1.5, d: 1.3 } as const;
  const CAB = { w: 1.0, h: 1.25, d: 1.3 } as const;
  const HOOD = { w: 0.9, h: 0.85, d: 1.2 } as const;
  const WHEEL_R = 0.28;
  const WHEEL_T = 0.22;
  const WHEEL_Y = -0.55;

  return (
    <group ref={ref} position={[0, -0.05, 0]} rotation={[0.12, -0.45, 0]}>
      {/* Trailer body */}
      <WireBox
        size={[TRAILER.w, TRAILER.h, TRAILER.d]}
        position={[-1.0, 0.3, 0]}
        color={lineColor}
      />
      {/* Cab (sleeper) */}
      <WireBox
        size={[CAB.w, CAB.h, CAB.d]}
        position={[1.0, 0.175, 0]}
        color={lineColor}
      />
      {/* Hood (engine) */}
      <WireBox
        size={[HOOD.w, HOOD.h, HOOD.d * 0.95]}
        position={[1.85, -0.05, 0]}
        color={lineColor}
      />
      {/* Chassis rail connecting cab & trailer */}
      <WireBox
        size={[5.0, 0.08, 0.9]}
        position={[0.1, -0.4, 0]}
        color={lineColor}
      />
      {/* Wheels — 4 axles, 2 per side (tractor front, drive, trailer front, trailer rear) */}
      {(
        [
          [2.2, 0.55],
          [2.2, -0.55],
          [0.6, 0.55],
          [0.6, -0.55],
          [-1.4, 0.55],
          [-1.4, -0.55],
          [-2.3, 0.55],
          [-2.3, -0.55],
        ] as const
      ).map((p, i) => (
        <WireCylinder
          key={i}
          radius={WHEEL_R}
          height={WHEEL_T}
          position={[p[0], WHEEL_Y, p[1]]}
          color={lineColor}
        />
      ))}
      {/* Windshield accent */}
      <WireBox
        size={[0.12, 0.7, 1.2]}
        position={[1.51, 0.35, 0]}
        color={lineColor}
      />
    </group>
  );
}

export default function MiniTruckScene({ color, pulse }: Props) {
  return (
    <div className="relative h-[170px] w-full overflow-hidden bg-gradient-to-b from-ink-100/60 via-ink-50/30 to-white">
      {/* subtle grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(15,23,42,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,0.04) 1px, transparent 1px)",
          backgroundSize: "18px 18px",
          maskImage:
            "radial-gradient(ellipse at center, black 55%, transparent 85%)",
        }}
      />
      <Canvas
        camera={{ position: [3.2, 2.0, 4.6], fov: 38 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={0.4} />
        <Truck color={color} pulse={pulse} />
      </Canvas>
      {/* soft fade at the bottom */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white to-transparent" />
    </div>
  );
}
