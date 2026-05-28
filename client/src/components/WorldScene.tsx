import { MapControls, PerspectiveCamera } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import type { WorldSnapshot } from "../types";
import { layoutPosition, SCENE_SCALE, toScene } from "../worldCoords";
import { AgentAvatar } from "./AgentAvatar";
import { LandmarkBuilding } from "./LandmarkBuilding";

/** Marina / east-coast water (design coords → spread world coords, radius in world units) */
const WATER_PATCHES: [number, number, number][] = [
  [144, 150, 5],
  [186, 124, 4],
  [156, 160, 4.5],
].map(([dx, dz, r]) => {
  const [wx, wz] = layoutPosition(dx, dz);
  return [wx, wz, r] as [number, number, number];
});

export function WorldScene({ snapshot }: { snapshot: WorldSnapshot }) {
  return (
    <Canvas shadows className="world-canvas" gl={{ antialias: true }}>
      <PerspectiveCamera
        makeDefault
        position={[14, 14, 14]}
        fov={45}
        near={0.1}
        far={500}
      />
      <MapControls
        enableRotate
        enablePan
        enableZoom
        maxPolarAngle={Math.PI / 2.15}
        minPolarAngle={0.25}
        target={[0, 0, 0]}
        maxDistance={72}
        minDistance={4}
      />
      <color attach="background" args={["#87CEEB"]} />
      <fog attach="fog" args={["#b8d4e8", 28, 85]} />
      <hemisphereLight args={["#fff8e7", "#2d6a4f", 0.65]} />
      <ambientLight intensity={0.55} />
      <directionalLight
        castShadow
        position={[12, 20, 8]}
        intensity={1.2}
        shadow-mapSize={[1024, 1024]}
      />
      {/* Land mass */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.01, 0]}>
        <planeGeometry args={[42, 42]} />
        <meshStandardMaterial color="#c8d4b8" roughness={0.95} />
      </mesh>
      {/* East — straits / marina water */}
      {WATER_PATCHES.map(([wx, wz, r], i) => {
        const [x, , z] = toScene(wx, wz);
        return (
          <mesh
            key={i}
            rotation={[-Math.PI / 2, 0, 0]}
            position={[x, 0.02, z]}
          >
            <circleGeometry args={[r * SCENE_SCALE, 24]} />
            <meshStandardMaterial
              color="#0096c7"
              transparent
              opacity={0.82}
              metalness={0.15}
              roughness={0.15}
            />
          </mesh>
        );
      })}
      <gridHelper args={[40, 40, "#8a9a7a", "#9aad8c"]} position={[0, 0.03, 0]} />
      {snapshot.landmarks.map((lm) => (
        <LandmarkBuilding key={lm.id} landmark={lm} />
      ))}
      {(snapshot.bricks ?? []).map((b, i) => {
        const [x, , z] = toScene(b.x, b.z);
        return (
          <mesh key={`brick-${i}`} position={[x, 0.2, z]} castShadow>
            <boxGeometry args={[0.35, 0.35, 0.35]} />
            <meshStandardMaterial color={b.color} />
          </mesh>
        );
      })}
      {snapshot.agents
        .filter((agent) => agent.alive !== false)
        .map((agent) => (
          <AgentAvatar key={agent.name} agent={agent} />
        ))}
    </Canvas>
  );
}
