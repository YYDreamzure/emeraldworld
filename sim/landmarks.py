import math
from dataclasses import dataclass
from pathlib import Path

from sim.config import ROOT
from sim.singapore import (
    SINGAPORE_LANDMARKS,
    SINGAPORE_POSITIONS,
    layout_position,
)


@dataclass(frozen=True)
class Landmark:
    id: str
    name: str
    description: str
    x: float
    z: float
    building_type: str = "default"


def _fallback_title(slug: str) -> str:
    return slug.replace("_", " ").title()


def _fallback_description(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Description"):
            continue
        if line.startswith("## ") and line != "## Description":
            break
        if line.strip() and not line.startswith("#"):
            return line.strip()
    return ""


def load_landmarks() -> list[Landmark]:
    landmarks_dir = ROOT / "landmarks"
    positions = dict(SINGAPORE_POSITIONS)

    paths = [p for p in sorted(landmarks_dir.glob("*.md")) if p.name != "README.md"]
    unplaced = [p.stem for p in paths if p.stem not in positions]
    for i, slug in enumerate(unplaced):
        angle = (i / max(len(unplaced), 1)) * math.tau
        positions[slug] = (
            120.0 + 28 * math.cos(angle),
            120.0 + 28 * math.sin(angle),
        )

    items: list[Landmark] = []
    for path in paths:
        slug = path.stem
        sg = SINGAPORE_LANDMARKS.get(slug)
        if sg:
            name, desc, btype = sg
        else:
            name = _fallback_title(slug)
            desc = _fallback_description(path)
            btype = "default"
        x, z = layout_position(*positions[slug])
        items.append(
            Landmark(
                id=slug,
                name=name,
                description=desc,
                x=x,
                z=z,
                building_type=btype,
            )
        )
    return items


LANDMARKS = load_landmarks()
LANDMARK_BY_ID = {lm.id: lm for lm in LANDMARKS}
LANDMARK_BY_NAME = {lm.name.lower(): lm for lm in LANDMARKS}
