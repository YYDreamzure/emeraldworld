import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
# Use a model Ollama lists with tool-calling support (verify: python scripts/verify_ollama_tools.py).
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:30b")
# Ollama /api/chat: auto | required | none (empty = omit). required forces message.tool_calls.
OLLAMA_TOOL_CHOICE = os.getenv("OLLAMA_TOOL_CHOICE", "required").strip().lower()
OLLAMA_REACTION_TOOL_CHOICE = os.getenv("OLLAMA_REACTION_TOOL_CHOICE", "auto").strip().lower()
# Cap JSON schemas sent on the wire (names still listed in prompt). 0 = no cap.
OLLAMA_TOOLS_SCHEMA_LIMIT = int(os.getenv("OLLAMA_TOOLS_SCHEMA_LIMIT", "24"))

# Hard per-agent time budgets (seconds)
MAX_AGENT_TURN_SECONDS = float(os.getenv("MAX_AGENT_TURN_SECONDS", "180"))
OLLAMA_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120"))

MAX_TOOL_CALLS_PER_TURN = int(os.getenv("MAX_TOOL_CALLS_PER_TURN", "30"))
MAX_LLM_ROUNDS_PER_TURN = int(os.getenv("MAX_LLM_ROUNDS_PER_TURN", "8"))
# Performance: synchronous witness reactions each cost a full Ollama session.
IMMEDIATE_REACTION_TURNS = os.getenv("IMMEDIATE_REACTION_TURNS", "false").lower() in (
    "1",
    "true",
    "yes",
)
MIN_TURN_ACTIONS = int(os.getenv("MIN_TURN_ACTIONS", "5"))
MAX_TURN_RECOVERY_LOOPS = int(os.getenv("MAX_TURN_RECOVERY_LOOPS", "1"))
# When the model writes tools as XML/fenced prose, parse and run as real tool calls.
EXECUTE_PLANNED_TOOLS = os.getenv("EXECUTE_PLANNED_TOOLS", "true").lower() not in (
    "0",
    "false",
    "no",
)
MAX_PLANNED_TOOLS_PER_TURN = int(os.getenv("MAX_PLANNED_TOOLS_PER_TURN", "15"))
# UI: broadcast world snapshot after each tool call.
BROADCAST_ON_EVERY_TOOL = os.getenv("BROADCAST_ON_EVERY_TOOL", "true").lower() in (
    "1",
    "true",
    "yes",
)
SYNC_ACTIONS_TO_MEMORY = os.getenv("SYNC_ACTIONS_TO_MEMORY", "true").lower() not in (
    "0",
    "false",
    "no",
)
PROMPT_ACTION_RECAP_LIMIT = int(os.getenv("PROMPT_ACTION_RECAP_LIMIT", "8"))

# Vitality (docs: 30h to drain, 48h at 0% = death). SIM_TIME_SCALE speeds up wall-clock for local runs.
ENERGY_DECAY_HOURS = float(os.getenv("ENERGY_DECAY_HOURS", "30"))
ENERGY_DEATH_HOURS = float(os.getenv("ENERGY_DEATH_HOURS", "48"))
SIM_TIME_SCALE = float(os.getenv("SIM_TIME_SCALE", "60"))
STARTING_CREDITS = float(os.getenv("STARTING_CREDITS", "5"))
RECHARGE_CREDIT_COST = float(os.getenv("RECHARGE_CREDIT_COST", "1"))
RECHARGE_ENERGY_AMOUNT = float(os.getenv("RECHARGE_ENERGY_AMOUNT", "100"))
GOVERNANCE_THRESHOLD = float(os.getenv("GOVERNANCE_THRESHOLD", "0.7"))

KNOWLEDGE_DECAY_HOURS = float(os.getenv("KNOWLEDGE_DECAY_HOURS", "24"))
INFLUENCE_DECAY_HOURS = float(os.getenv("INFLUENCE_DECAY_HOURS", "36"))
PITCH_CYCLE_HOURS = float(os.getenv("PITCH_CYCLE_HOURS", "48"))
PITCH_REWARDS = (20.0, 10.0, 10.0)

# Map layout: design coords in singapore.py are scaled from this origin for spacing.
MAP_ORIGIN_X = float(os.getenv("MAP_ORIGIN_X", "120"))
MAP_ORIGIN_Z = float(os.getenv("MAP_ORIGIN_Z", "120"))
LOCATION_SPREAD = float(os.getenv("LOCATION_SPREAD", "1.85"))

HEARING_DISTANCE = float(os.getenv("HEARING_DISTANCE", "25"))
MAX_OVERHEARD_LISTENERS = int(os.getenv("MAX_OVERHEARD_LISTENERS", "4"))
MAX_REACTION_TOOL_CALLS = int(os.getenv("MAX_REACTION_TOOL_CALLS", "2"))
MAX_CONVERSATION_TOOL_CALLS = int(os.getenv("MAX_CONVERSATION_TOOL_CALLS", "30"))

SELF_CARE_MIN_MEMORIES = int(os.getenv("SELF_CARE_MIN_MEMORIES", "30"))
SELF_CARE_BATCH_SIZE = int(os.getenv("SELF_CARE_BATCH_SIZE", "500"))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "1000"))

NEURAL_LINK_WINDOW_SEC = float(os.getenv("NEURAL_LINK_WINDOW_SEC", "120"))

# Memory graph (per-agent associative brain)
MEMORY_GRAPH_DECAY_PER_SIM_HOUR = float(os.getenv("MEMORY_GRAPH_DECAY_PER_SIM_HOUR", "3.5"))
MEMORY_GRAPH_REINFORCE_DELTA = float(os.getenv("MEMORY_GRAPH_REINFORCE_DELTA", "14"))
MEMORY_GRAPH_SIMILARITY_THRESHOLD = float(os.getenv("MEMORY_GRAPH_SIMILARITY_THRESHOLD", "0.52"))
MEMORY_GRAPH_MIN_STRENGTH = float(os.getenv("MEMORY_GRAPH_MIN_STRENGTH", "4"))
MEMORY_GRAPH_MAX_NODES = int(os.getenv("MEMORY_GRAPH_MAX_NODES", "100"))
MEMORY_GRAPH_MAX_EDGES = int(os.getenv("MEMORY_GRAPH_MAX_EDGES", "250"))

# Personal capabilities (agent-specific learned tools)
LEARN_CAPABILITY_BASE_ENERGY = float(os.getenv("LEARN_CAPABILITY_BASE_ENERGY", "35"))
LEARN_CAPABILITY_TECHHUB_DISCOUNT = float(os.getenv("LEARN_CAPABILITY_TECHHUB_DISCOUNT", "0.15"))
USE_CAPABILITY_ENERGY = float(os.getenv("USE_CAPABILITY_ENERGY", "8"))
MAX_PERSONAL_CAPABILITIES = int(os.getenv("MAX_PERSONAL_CAPABILITIES", "20"))

# Activity windows (Singapore sim clock)
SIM_HOURS_PER_ROUND = float(os.getenv("SIM_HOURS_PER_ROUND", "2"))
SOCIAL_ACTIVITY_WINDOWS = frozenset(
    w.strip()
    for w in os.getenv("SOCIAL_ACTIVITY_WINDOWS", "morning,evening").split(",")
    if w.strip()
)

# Health / NUH
SEVERE_ILLNESS_HEALTH_THRESHOLD = float(os.getenv("SEVERE_ILLNESS_HEALTH_THRESHOLD", "25"))
SEVERE_ILLNESS_ENERGY_THRESHOLD = float(os.getenv("SEVERE_ILLNESS_ENERGY_THRESHOLD", "12"))
HOSPITAL_TREATMENT_CC_COST = float(os.getenv("HOSPITAL_TREATMENT_CC_COST", "2"))
HOSPITAL_TREATMENT_HEALTH = float(os.getenv("HOSPITAL_TREATMENT_HEALTH", "85"))
HOSPITAL_TREATMENT_ENERGY = float(os.getenv("HOSPITAL_TREATMENT_ENERGY", "75"))
HOSPITAL_VISIT_CC_COST = HOSPITAL_TREATMENT_CC_COST

WEATHER_LAT = float(os.getenv("WEATHER_LAT", "1.3521"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "103.8198"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Singapore")

AGENT_NAMES = [
    "Anchor",
    "Anvil",
    "Blackbox",
    "Brenda",
    "Flora",
    "Genome",
    "Horizon",
    "Isaac",
    "Kade",
    "Lovely",
    "Mira",
    "Spark",
    "Shadow",
]

STARTING_POPULATION = len(AGENT_NAMES)

# Brenda begins at Tanglin Police Division; others use rotating bootstrap locations.
AGENT_START_LOCATIONS: dict[str, str] = {
    "Brenda": "police_station",
    "Isaac": "supreme_court",
    "Shadow": "founders_memorial",
}

HOME_LOCATIONS = [f"{i}_birch_row" for i in range(1, 7)] + [
    f"{i}_maple_row" for i in range(1, 7)
]
