# Local simulation vs production

> **Full guide:** [`LOCAL_SIMULATION.md`](../LOCAL_SIMULATION.md) — setup, API, modules, env vars, tools, persistence, troubleshooting.

The `sim/` + `client/` stack implements the **design in this docs folder** for local development (Ollama, JSONL run storage). Production Season 1 worlds add PostgreSQL, 15-day 1:1 wall-clock runs, multi-model routing, and Google TTS.

## Coverage matrix

| Doc | Feature | Local `sim/` status |
|-----|---------|---------------------|
| **ARCHITECTURE** | React Three Fiber world | ✅ `client/` |
| | WebSocket live view | ✅ `/ws` |
| | Blogs / Newspaper UI | ✅ Blogs & News tab |
| | FastAPI backend | ✅ `sim/server.py` |
| | PostgreSQL persistence | ❌ → `results/runs/*.jsonl` |
| | 15-day continuous run | ❌ → configurable rounds |
| | TTS / Chirp3-HD | ❌ |
| | Multi-provider LLM routing | ❌ → Ollama only |
| **ORCHESTRATION** | Round-robin, 1 agent at a time | ✅ |
| | Boost queue (1 CC) | ✅ `boost_turn` |
| | Reactive overhearing | ✅ `sim/reactive.py` |
| | Energy / knowledge / influence needs | ✅ `sim/needs.py` |
| | Turn tool budgets | ✅ regular=30, reaction=2 |
| | System characters (TH/Blog/Reporter admin) | ⚠️ Reporter = newspaper digest; no LLM admin agents |
| | NYC 1:1 real-time | ⚠️ `SIM_TIME_SCALE` + Singapore TZ; weather via Open-Meteo |
| **MEMORY** | Long-term memory + IDs | ✅ |
| | Soul entries | ✅ |
| | Self-care summarization | ✅ Ollama batch summary |
| | Diary | ✅ |
| | Conversation history | ✅ |
| | Relationship graph | ✅ `RelationshipRecord` |
| | Neural link 2-min window | ✅ |
| **GOVERNANCE** | 70% threshold | ✅ |
| | Proposal categories | ✅ constitution/resource/infrastructure/others/removal |
| | Comments / updates | ✅ |
| | awaiting_clarification | ✅ |
| | Implementation + final report | ✅ |
| | Complaints | ✅ |
| | Brenda law enforcement (event log, enforcement proposals) | ✅ |
| | Isaac judiciary (Supreme Court, Changi Prison, sentencing) | ✅ |
| | Personal capabilities (learn private tools, energy cost) | ✅ |
| | Activity windows + social talk periods | ✅ |
| | call/message afar; say_to_agent co-located only | ✅ |
| | NUH hospital treatment | ✅ |
| | Shadow covert referrals to Isaac | ✅ |
| **ECONOMY** | Recharge 1 CC | ✅ |
| | Pay agent | ✅ `pay_agent` |
| | Pitch cycle + rewards | ✅ `sim/economy.py` |
| | Evidence URL / disqualify | ✅ |
| | Research grants on accept | ✅ `grant_amount` on proposal |
| **Tools** | 128 tool catalog | ✅ `tools_catalog.py` + `tools_exec.py` |

## Intentionally out of scope (local)

- PostgreSQL 60+ tables
- Production em-agent-framework / Vertex / Anthropic / OpenAI / xAI routing
- 54 distinct 3D animation rigs (gestures + speech bubbles only)
- Image generation API (Gemini) — recorded stub only
- Live `web_fetch` to arbitrary URLs — simulated summaries

## Run

```bash
python -m sim.server
cd client && npm run dev
```

See root `README.md` for environment variables (`SIM_TIME_SCALE`, `OLLAMA_MODEL`, etc.).
