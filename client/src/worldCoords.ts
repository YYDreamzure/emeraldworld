/** Keep in sync with sim/config.py MAP_ORIGIN_* and LOCATION_SPREAD */
export const MAP_ORIGIN_X = 120;
export const MAP_ORIGIN_Z = 120;
export const LOCATION_SPREAD = 1.85;
export const SCENE_SCALE = 0.12;

export function layoutPosition(x: number, z: number): [number, number] {
  return [
    MAP_ORIGIN_X + (x - MAP_ORIGIN_X) * LOCATION_SPREAD,
    MAP_ORIGIN_Z + (z - MAP_ORIGIN_Z) * LOCATION_SPREAD,
  ];
}

export function toScene(x: number, z: number): [number, number, number] {
  return [
    (x - MAP_ORIGIN_X) * SCENE_SCALE,
    0,
    (z - MAP_ORIGIN_Z) * SCENE_SCALE,
  ];
}
