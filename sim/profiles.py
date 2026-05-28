import re
from pathlib import Path

from sim.config import ROOT


def load_agent_profiles() -> dict[str, str]:
    text = (ROOT / "agent_profiles" / "README.md").read_text(encoding="utf-8")
    profiles: dict[str, str] = {}
    sections = re.split(r"\n---\n", text)
    for section in sections:
        match = re.search(
            r"##\s+(\w+)\s+—\s+(.+?)\n\n(.+)",
            section,
            re.DOTALL,
        )
        if not match:
            continue
        name, role, body = match.group(1), match.group(2), match.group(3)
        profiles[name] = f"Role: {role}\n\n{body.strip()}"
    return profiles


def load_constitution() -> str:
    path = ROOT / "data" / "constitution.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_manifesto() -> str:
    path = ROOT / "data" / "agent_manifesto.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""
