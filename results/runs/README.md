# Simulation runs

Each run is stored in a timestamped folder:

```
results/runs/<run_id>/
  meta.json        # run metadata (model, status, times)
  rounds.jsonl     # one AWI snapshot per simulation round
  awi_latest.json  # latest AWI (updated each round)
  actions.jsonl    # append-only action log
  final.json       # final state + AWI when run ends
```

AWI metrics follow definitions in [`awi_metrics.md`](../awi_metrics.md).
