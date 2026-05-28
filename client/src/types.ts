export interface Landmark {
  id: string;
  name: string;
  x: number;
  z: number;
  description: string;
  buildingType?: string;
}

export interface MemoryBrainNode {
  id: string;
  text: string;
  strength: number;
  reinforcementCount: number;
  protected: boolean;
  source?: string;
  accessCount?: number;
}

export interface MemoryBrainEdge {
  id?: string;
  a: string;
  b: string;
  weight: number;
}

export interface MemoryBrain {
  nodeCount: number;
  edgeCount: number;
  protectedCount: number;
  top?: MemoryBrainNode[];
  nodes?: MemoryBrainNode[];
  edges?: MemoryBrainEdge[];
}

export interface PersonalTool {
  id: string;
  toolId: string;
  owner: string;
  name: string;
  purpose: string;
  whyDeveloped: string;
  effectType: string;
  effectLabel?: string;
  systemEffect?: string;
  durationHours: number;
  learnEnergyCost: number;
  useEnergyCost: number;
  timesUsed: number;
  learnedAt: number;
  privateToOwner?: boolean;
}

export interface AgentStats {
  totalActions: number;
  toolsUsed: number;
  locationsVisited: number;
  lastActionTs: number | null;
}

export interface Agent {
  name: string;
  role: string;
  color: string;
  portrait: string;
  locationId: string;
  locationName: string;
  homeName?: string;
  x: number;
  z: number;
  mood: string;
  energy: number;
  knowledge?: number;
  influence?: number;
  credits: number;
  gesture?: string | null;
  displayName?: string;
  alive: boolean;
  energyStatus: "ok" | "low" | "critical" | "dead";
  hoursAtZero?: number;
  hoursUntilDeath?: number | null;
  deathCause?: string | null;
  speech: string | null;
  emoticon: string | null;
  isActive: boolean;
  memories: string[];
  memoryBrain?: MemoryBrain;
  thoughts?: ActionRecord[];
  planLog?: ActionRecord[];
  speechLog?: ActionRecord[];
  toolLog?: ActionRecord[];
  actionLog?: ActionRecord[];
  personalTools?: PersonalTool[];
  todos: string[];
  stats: AgentStats;
}

export interface Proposal {
  id: string;
  kind: string;
  proposer: string;
  targetAgent: string;
  reason: string;
  status: string;
  votesFor: number;
  votesAgainst: number;
  votesNeeded: number;
  tick: number;
}

export interface ActionRecord {
  id: string;
  tick: number;
  ts: number;
  agent: string;
  kind: string;
  summary: string;
  detail?: string | null;
  tool: string | null;
  location: string | null;
  target: string | null;
  ok: boolean;
  args?: Record<string, string | number | boolean>;
  /** Complete thought/plan body for Agents tab (never abbreviated). */
  fullText?: string | null;
}

export interface WorldEvent {
  id: string;
  tick: number;
  ts: number;
  status: "ongoing" | "completed";
  kind: string;
  title: string;
  summary: string;
  agents: string[];
  endedTick: number | null;
  endedTs: number | null;
}

export interface DashboardData {
  summary: {
    tick: number;
    running: boolean;
    activeAgent: string | null;
    ongoingEventCount: number;
    totalActions: number;
    totalEvents: number;
    aliveCount?: number;
  };
  ongoingEvents: WorldEvent[];
  recentEvents: WorldEvent[];
  agents: Record<
    string,
    {
      actions: ActionRecord[];
      events?: WorldEvent[];
      stats: AgentStats;
    }
  >;
}

export interface AwiMetric {
  id: string;
  name: string;
  value: number;
  unit?: string;
  breakEven?: number;
  change?: number;
  note?: string;
  detail?: Record<string, unknown>;
}

export interface AwiSnapshot {
  round: number;
  tick: number;
  computedAt: number;
  metrics: Record<string, AwiMetric>;
  perAgent?: Record<string, unknown>;
}

export interface BlogPost {
  id: string;
  title: string;
  author: string;
  content: string;
}

export interface NewspaperEdition {
  headline: string;
  articles: { title: string; author: string }[];
  ts?: number;
  reporter?: string;
}

export interface WorldSnapshot {
  tick: number;
  round?: number;
  runId?: string;
  startedAt?: number;
  running: boolean;
  activeAgent: string | null;
  model: string;
  awi?: AwiSnapshot;
  population?: { alive: number; total: number };
  landmarks: Landmark[];
  agents: Agent[];
  proposals?: Proposal[];
  weather?: string;
  blogs?: BlogPost[];
  newspaper?: NewspaperEdition[];
  billboard?: { id: string; author: string; content: string }[];
  bricks?: { x: number; z: number; color: string; agent: string }[];
  burnedLocations?: string[];
  log: string[];
  dashboard: DashboardData;
  personalToolsIndex?: PersonalTool[];
}
