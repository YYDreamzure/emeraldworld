import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import type { Agent } from "../types";
import { toScene } from "../worldCoords";

export function AgentAvatar({ agent }: { agent: Agent }) {
  if (agent.alive === false) return null;
  const group = useRef<THREE.Group>(null);
  const target = useRef(new THREE.Vector3(...toScene(agent.x, agent.z)));

  useFrame((_, delta) => {
    if (!group.current) return;
    target.current.set(...toScene(agent.x, agent.z));
    group.current.position.lerp(target.current, Math.min(1, delta * 4));
    if (agent.gesture === "dance" || agent.isActive) {
      group.current.position.y =
        0.15 + Math.sin(performance.now() * 0.004) * 0.08;
    } else {
      group.current.position.y = THREE.MathUtils.lerp(
        group.current.position.y,
        0,
        delta * 6,
      );
    }
  });

  const [sx, , sz] = toScene(agent.x, agent.z);
  const label = agent.emoticon || agent.speech;

  return (
    <group ref={group} position={[sx, 0, sz]}>
      <mesh castShadow position={[0, 0.45, 0]}>
        <capsuleGeometry args={[0.28, 0.45, 6, 16]} />
        <meshStandardMaterial
          color={agent.color}
          emissive={
            agent.energyStatus === "critical"
              ? "#e63946"
              : agent.energyStatus === "low"
                ? "#ffd166"
                : agent.color
          }
          emissiveIntensity={agent.isActive ? 0.55 : agent.energyStatus === "critical" ? 0.5 : 0.15}
        />
      </mesh>
      <mesh position={[0, 1.05, 0]}>
        <sphereGeometry args={[0.26, 16, 16]} />
        <meshStandardMaterial color="#e8e6e3" roughness={0.4} />
      </mesh>
      {agent.isActive && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
          <ringGeometry args={[0.35, 0.42, 32]} />
          <meshBasicMaterial color="#ff8c00" transparent opacity={0.8} />
        </mesh>
      )}
      {label && (
        <Html
          position={[0, 1.35, 0]}
          center
          distanceFactor={8}
          style={{ pointerEvents: "none" }}
        >
          <div className="speech-bubble">
            {agent.emoticon ? (
              <span className="emoticon">{agent.emoticon}</span>
            ) : (
              <span>
                {(agent.speech?.length ?? 0) > 140
                  ? `${agent.speech!.slice(0, 140)}…`
                  : agent.speech}
              </span>
            )}
          </div>
        </Html>
      )}
      <Html position={[0, -0.15, 0]} center distanceFactor={10}>
        <div className={`agent-label ${agent.isActive ? "active" : ""}`}>
          {agent.name}
        </div>
      </Html>
    </group>
  );
}
