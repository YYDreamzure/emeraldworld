"""Singapore-themed names, layout, and aliases for Emergence World."""

from __future__ import annotations

from sim.config import LOCATION_SPREAD, MAP_ORIGIN_X, MAP_ORIGIN_Z


def layout_position(x: float, z: float) -> tuple[float, float]:
    """Scale design coordinates away from the map origin (wider landmark spacing)."""
    return (
        MAP_ORIGIN_X + (x - MAP_ORIGIN_X) * LOCATION_SPREAD,
        MAP_ORIGIN_Z + (z - MAP_ORIGIN_Z) * LOCATION_SPREAD,
    )

# id -> (display name, short description, building type for 3D viewer)
SINGAPORE_LANDMARKS: dict[str, tuple[str, str, str]] = {
    "central_plaza": (
        "Raffles Place",
        "The civic heart of the CBD — agents gather near the Merlion overlook.",
        "civic",
    ),
    "town_hall": (
        "City Hall",
        "Governance and Town Hall proposals happen near the Padang.",
        "civic",
    ),
    "public_library": (
        "National Library",
        "Research, archives, and deep reading in the civic district.",
        "civic",
    ),
    "central_park": (
        "Botanic Gardens",
        "Tropical greenery and open lawns — UNESCO heritage vibes.",
        "park",
    ),
    "agent_billboard": (
        "Orchard Road",
        "Shopping belt billboard — public posts and street buzz.",
        "mall",
    ),
    "agent_techhub": (
        "one-north",
        "Fusionopolis tech hub — tools, code, and agent R&D.",
        "tech",
    ),
    "victory_arch": (
        "Marina Bay Sands",
        "Iconic triple-tower skyline — grant pitches and Victory Arch cycles.",
        "hotel",
    ),
    "bookworm": (
        "Bras Basah",
        "Books, archives, and quiet intel in the arts district.",
        "mall",
    ),
    "bean_and_brew_charging_station": (
        "Maxwell Food Centre",
        "Kopitiam recharge — coffee, kaya toast, energy top-up.",
        "hawker",
    ),
    "riverside_park": (
        "Singapore River",
        "Boat quays and riverside walks from Clarke Quay upstream.",
        "water",
    ),
    "founders_memorial": (
        "Founders' Memorial",
        "Bay East Garden memorial — history and reflection.",
        "civic",
    ),
    "police_station": (
        "Tanglin Police Division",
        "Complaints, order, and rule enforcement.",
        "civic",
    ),
    "supreme_court": (
        "Supreme Court",
        "Judge Isaac hears enforcement cases and passes sentence under Singapore law.",
        "court",
    ),
    "changi_prison": (
        "Changi Prison",
        "Custodial sentences — jailed agents serve time here.",
        "prison",
    ),
    "community_garden": (
        "Community Garden @ Bishan",
        "Allotments and neighbourhood green fingers.",
        "park",
    ),
    "business_tower": (
        "CBD Tower",
        "Corporate offices overlooking Shenton Way.",
        "tower",
    ),
    "gamestop_arena": (
        "Indoor Stadium",
        "Esports and events hall — east side.",
        "arena",
    ),
    "fitlife_club": (
        "ActiveSG Gym",
        "Fitness, popularity checks, and health stats.",
        "mall",
    ),
    "lighthouse_point": (
        "Sentosa Point",
        "Coastal lookout and island escape.",
        "water",
    ),
    "sky_wheel": (
        "Singapore Flyer",
        "Giant observation wheel on the bay fringe.",
        "landmark",
    ),
    "sunset_pier": (
        "Clarke Quay",
        "Waterfront pier, nightlife, and evening gatherings.",
        "water",
    ),
    "human_center": (
        "ServiceSG Centre",
        "Human consultation and task handoff.",
        "civic",
    ),
    "national_university_hospital": (
        "National University Hospital",
        "Acute care for severely ill agents — stabilisation and recovery.",
        "hospital",
    ),
    "town_center_mall": (
        "VivoCity",
        "Harbourfront mall — retail and crowds.",
        "mall",
    ),
}

for i in range(1, 7):
    SINGAPORE_LANDMARKS[f"{i}_birch_row"] = (
        f"Punggol HDB {100 + i}",
        f"Residential block along Punggol Waterway — home {i}.",
        "hdb",
    )
    SINGAPORE_LANDMARKS[f"{i}_maple_row"] = (
        f"Tampines HDB {200 + i}",
        f"Heartland block near Tampines MRT — home {i}.",
        "hdb",
    )

# Design layout on ~240 grid (east = higher x, north = lower z).
# Runtime positions apply layout_position() — see LOCATION_SPREAD in config.
SINGAPORE_POSITIONS: dict[str, tuple[float, float]] = {
    "victory_arch": (130.0, 168.0),
    "sunset_pier": (156.0, 160.0),
    "riverside_park": (144.0, 150.0),
    "sky_wheel": (150.0, 156.0),
    "central_plaza": (120.0, 120.0),
    "town_hall": (106.0, 134.0),
    "business_tower": (130.0, 106.0),
    "town_center_mall": (100.0, 134.0),
    "agent_billboard": (92.0, 92.0),
    "bookworm": (84.0, 88.0),
    "bean_and_brew_charging_station": (86.0, 110.0),
    "agent_techhub": (70.0, 118.0),
    "founders_memorial": (66.0, 148.0),
    "public_library": (142.0, 118.0),
    "central_park": (118.0, 82.0),
    "community_garden": (140.0, 86.0),
    "lighthouse_point": (186.0, 124.0),
    "gamestop_arena": (178.0, 106.0),
    "fitlife_club": (168.0, 96.0),
    "human_center": (136.0, 136.0),
    "police_station": (104.0, 144.0),
    "supreme_court": (96.0, 136.0),
    "changi_prison": (194.0, 118.0),
    "national_university_hospital": (112.0, 100.0),
}

for i in range(1, 7):
    SINGAPORE_POSITIONS[f"{i}_birch_row"] = (76.0 + i * 7.0, 60.0)
    SINGAPORE_POSITIONS[f"{i}_maple_row"] = (140.0 + i * 7.0, 64.0)

# Alternate names agents may use in go_to_place
NAME_ALIASES: dict[str, str] = {}
for slug, (name, _, _) in SINGAPORE_LANDMARKS.items():
    NAME_ALIASES[name.lower()] = slug
    NAME_ALIASES[slug.replace("_", " ")] = slug

NAME_ALIASES.update(
    {
        "marina bay sands": "victory_arch",
        "mbs": "victory_arch",
        "marina bay": "victory_arch",
        "raffles place": "central_plaza",
        "orchard": "agent_billboard",
        "orchard road": "agent_billboard",
        "botanic gardens": "central_park",
        "gardens by the bay": "central_park",
        "clarke quay": "sunset_pier",
        "singapore river": "riverside_park",
        "vivo city": "town_center_mall",
        "vivocity": "town_center_mall",
        "one north": "agent_techhub",
        "fusionopolis": "agent_techhub",
        "sentosa": "lighthouse_point",
        "flyer": "sky_wheel",
        "singapore flyer": "sky_wheel",
        "maxwell": "bean_and_brew_charging_station",
        "kopitiam": "bean_and_brew_charging_station",
        "hawker centre": "bean_and_brew_charging_station",
        "national library": "public_library",
        "city hall": "town_hall",
        "town hall": "town_hall",
        "supreme court": "supreme_court",
        "high court": "supreme_court",
        "changi": "changi_prison",
        "changi prison": "changi_prison",
        "prison": "changi_prison",
        "nuh": "national_university_hospital",
        "national university hospital": "national_university_hospital",
        "hospital": "national_university_hospital",
        "hdb": "1_birch_row",
        "punggol": "1_birch_row",
        "tampines": "1_maple_row",
    }
)

WORLD_BLURB = (
    "Emergence World is set in a stylised Singapore: humid tropics, HDB heartlands, "
    "the CBD, Marina Bay, kopitiams, and MRT-thinking agents who move between hawker "
    "centres, libraries, and one-north. Time and weather follow Singapore (UTC+8)."
)
