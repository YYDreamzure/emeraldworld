import { Html } from "@react-three/drei";
import type { Landmark } from "../types";
import { toScene } from "../worldCoords";

type BuildingType =
  | "hdb"
  | "hotel"
  | "tower"
  | "mall"
  | "park"
  | "water"
  | "hawker"
  | "civic"
  | "tech"
  | "arena"
  | "landmark"
  | "court"
  | "prison"
  | "hospital"
  | "default";

const STYLES: Record<
  BuildingType,
  { color: string; roof?: string; height: number; wide?: boolean }
> = {
  hdb: { color: "#c9d6e3", roof: "#5a7a9a", height: 1.35, wide: true },
  hotel: { color: "#1e3a5f", roof: "#00a8e8", height: 1.7, wide: true },
  tower: { color: "#4a6fa5", roof: "#ffd166", height: 1.55 },
  mall: { color: "#e8dcc8", roof: "#e63946", height: 0.95, wide: true },
  park: { color: "#2d6a4f", height: 0.25 },
  water: { color: "#0077b6", height: 0.15 },
  hawker: { color: "#f4a261", roof: "#e76f51", height: 0.55, wide: true },
  civic: { color: "#f8f4e8", roof: "#6c757d", height: 1.2 },
  tech: { color: "#90be6d", roof: "#43aa8b", height: 1.0 },
  arena: { color: "#adb5bd", roof: "#495057", height: 0.85, wide: true },
  landmark: { color: "#caf0f8", roof: "#ff006e", height: 1.4 },
  court: { color: "#e8e4dc", roof: "#8b4513", height: 1.45, wide: true },
  prison: { color: "#495057", roof: "#212529", height: 1.0, wide: true },
  hospital: { color: "#f8f9fa", roof: "#e63946", height: 1.25, wide: true },
  default: { color: "#6c757d", roof: "#ff8c00", height: 0.85 },
};

function resolveType(lm: Landmark): BuildingType {
  const t = (lm.buildingType ?? "default") as BuildingType;
  return t in STYLES ? t : "default";
}

export function LandmarkBuilding({ landmark }: { landmark: Landmark }) {
  const [x, , z] = toScene(landmark.x, landmark.z);
  const type = resolveType(landmark);
  const style = STYLES[type];
  const isPark = type === "park";
  const isWater = type === "water";
  const w = style.wide ? 1.25 : 0.95;
  const d = style.wide ? 1.15 : 0.95;
  const h = style.height;

  if (isWater) {
    return (
      <group position={[x, 0.03, z]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[1.0, 16]} />
          <meshStandardMaterial
            color="#48cae4"
            transparent
            opacity={0.75}
            metalness={0.3}
            roughness={0.2}
          />
        </mesh>
        <Html position={[0, 0.4, 0]} center distanceFactor={14}>
          <div className="landmark-label">{landmark.name}</div>
        </Html>
      </group>
    );
  }

  if (isPark) {
    return (
      <group position={[x, 0, z]}>
        <mesh receiveShadow position={[0, 0.08, 0]}>
          <cylinderGeometry args={[1.15, 1.2, 0.18, 14]} />
          <meshStandardMaterial color={style.color} roughness={0.9} />
        </mesh>
        <mesh position={[0, 0.35, 0]}>
          <coneGeometry args={[0.35, 0.7, 6]} />
          <meshStandardMaterial color="#1b4332" />
        </mesh>
        <mesh position={[0.5, 0.3, 0.4]}>
          <coneGeometry args={[0.25, 0.5, 6]} />
          <meshStandardMaterial color="#40916c" />
        </mesh>
        <Html position={[0, 0.65, 0]} center distanceFactor={14}>
          <div className="landmark-label">{landmark.name}</div>
        </Html>
      </group>
    );
  }

  if (type === "hotel") {
    return (
      <group position={[x, 0, z]}>
        {[-0.35, 0, 0.35].map((ox, i) => (
          <mesh key={i} castShadow position={[ox, h / 2, 0]}>
            <boxGeometry args={[0.32, h, 0.5]} />
            <meshStandardMaterial color={style.color} roughness={0.5} />
          </mesh>
        ))}
        <mesh position={[0, h + 0.2, 0]}>
          <boxGeometry args={[1.1, 0.15, 0.55]} />
          <meshStandardMaterial
            color="#00b4d8"
            emissive="#00b4d8"
            emissiveIntensity={0.25}
          />
        </mesh>
        <Html position={[0, h + 0.65, 0]} center distanceFactor={14}>
          <div className="landmark-label sg">{landmark.name}</div>
        </Html>
      </group>
    );
  }

  if (type === "hdb") {
    return (
      <group position={[x, 0, z]}>
        <mesh castShadow position={[0, h / 2, 0]}>
          <boxGeometry args={[w * 1.1, h, d * 0.9]} />
          <meshStandardMaterial color={style.color} roughness={0.75} />
        </mesh>
        {Array.from({ length: 4 }).map((_, row) =>
          Array.from({ length: 3 }).map((_, col) => (
            <mesh
              key={`${row}-${col}`}
              position={[
                (col - 1) * 0.28,
                0.25 + row * 0.28,
                d * 0.46,
              ]}
            >
              <planeGeometry args={[0.18, 0.14]} />
              <meshStandardMaterial
                color="#87ceeb"
                emissive="#87ceeb"
                emissiveIntensity={0.15}
              />
            </mesh>
          )),
        )}
        <Html position={[0, h + 0.45, 0]} center distanceFactor={14}>
          <div className="landmark-label">{landmark.name}</div>
        </Html>
      </group>
    );
  }

  return (
    <group position={[x, 0, z]}>
      <mesh castShadow receiveShadow position={[0, h / 2, 0]}>
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial color={style.color} roughness={0.65} />
      </mesh>
      {style.roof && (
        <mesh position={[0, h + 0.06, 0]}>
          <boxGeometry args={[w * 0.85, 0.1, d * 0.85]} />
          <meshStandardMaterial color={style.roof} />
        </mesh>
      )}
      <Html position={[0, h + 0.5, 0]} center distanceFactor={14}>
        <div className="landmark-label">{landmark.name}</div>
      </Html>
    </group>
  );
}
