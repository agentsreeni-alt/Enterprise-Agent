"""Run persistence. State is written to disk after every stage transition
(not just gate pauses), so a crash mid-run is resumable too -- the same
mechanism as a deliberate gate pause, just triggered differently.
"""

from __future__ import annotations

import json
from pathlib import Path

from enterprise_agent.pipeline.state import PipelineState

DEFAULT_RUNS_DIR = Path(".enterprise_agent/runs")


class RunStore:
    def __init__(self, runs_dir: Path = DEFAULT_RUNS_DIR):
        self.runs_dir = runs_dir

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def state_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "state.json"

    def config_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "config.json"

    def save_state(self, state: PipelineState) -> None:
        path = self.state_path(state.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), indent=2))

    def load_state(self, run_id: str) -> PipelineState:
        path = self.state_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"no run found with id {run_id}")
        return PipelineState.from_dict(json.loads(path.read_text()))

    def save_config(self, run_id: str, config: dict) -> None:
        """Persists the connector/LLM mode a run was *started* with, so a
        later `approve`/`reject` -- typically a fresh CLI process with its
        own freshly-constructed Orchestrator -- resumes with the exact same
        real/mock settings rather than silently falling back to whatever
        that new Orchestrator instance's defaults happen to be.
        """
        path = self.config_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2))

    def load_config(self, run_id: str) -> dict | None:
        path = self.config_path(run_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_runs(self) -> list[str]:
        if not self.runs_dir.exists():
            return []
        return sorted(
            p.name for p in self.runs_dir.iterdir() if (p / "state.json").exists()
        )
