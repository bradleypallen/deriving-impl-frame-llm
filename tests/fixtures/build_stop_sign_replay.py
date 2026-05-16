"""Builder for the committed ``stop_sign_replay.jsonl`` ReplayProvider fixture.

The fixture is generated *from* the committed stop-sign benchmark + the
production prompt-construction code, so it stays in sync with the
verification prompt template and context builders without a manual
update step.

A drift test (see ``tests/unit/test_replay_e2e.py``) regenerates the
fixture in a tmp file and asserts byte-equality with the committed one.
If the test fails, regenerate with:

    python -m tests.fixtures.build_stop_sign_replay
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infereval.benchmark import Benchmark
from infereval.context import resolve_context_builders
from infereval.endorsement import _expressions_for
from infereval.logging_setup import prompt_hash
from infereval.prompts import resolve_verification_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SIGN_BENCHMARK = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"
FIXTURE_PATH = Path(__file__).parent / "stop_sign_replay.jsonl"

# Per-item canned responses. Five samples per item so callers can run with
# ``n_samples=5``. The mix reflects realistic model output (varying surface
# form but consistent verdicts), so the parsing + majority-vote logic is
# exercised across cases.
RESPONSES_BY_ITEM_ID: dict[str, list[str]] = {
    "row-0": [
        "GOOD",
        "GOOD",
        "GOOD",
        "GOOD, since stop signs are red by convention.",
        "GOOD",
    ],
    "row-1": [
        "GOOD",
        "GOOD",
        "GOOD. Nighttime doesn't change the sign's color.",
        "GOOD",
        "GOOD",
    ],
    "row-2": [
        "GOOD",
        "GOOD. The sign still has its underlying red color.",
        "GOOD",
        "GOOD",
        "GOOD",
    ],
    "row-3": [
        "BAD",
        "BAD. The sign has been repainted blue.",
        "BAD",
        "BAD",
        "BAD",
    ],
}

# Provider identity baked into each record. Realistic but synthetic --
# we don't actually call anthropic here.
RECORDED_PROVIDER = "anthropic"
RECORDED_MODEL = "claude-haiku-4-5-20251001"
RECORDED_USAGE = {"input_tokens": 60, "output_tokens": 6}
RECORDED_WALL_TIME_MS = 120.0


def build_records() -> list[dict[str, Any]]:
    """Compute the list of fixture records from the committed benchmark."""
    bench = Benchmark.load(STOP_SIGN_BENCHMARK)
    bearers = bench.runtime_bearers()
    premise_builder, conclusion_builder = resolve_context_builders(bench.context_builders)
    prompt = resolve_verification_prompt(bench.verification_prompt)

    records: list[dict[str, Any]] = []
    for item in bench.items:
        impl = item.to_implication()
        prem_exprs = _expressions_for(impl.premises, bearers, strip_tex=True)
        conc_exprs = _expressions_for(impl.conclusions, bearers, strip_tex=True)
        premise_ctx = premise_builder(prem_exprs)
        conclusion_ctx = conclusion_builder(conc_exprs)
        user_text = prompt.build_user(premise_ctx, conclusion_ctx)
        ph = prompt_hash(user_text)

        responses = RESPONSES_BY_ITEM_ID.get(item.id)
        if responses is None:
            raise ValueError(
                f"No canned responses for item {item.id!r}; update "
                "RESPONSES_BY_ITEM_ID in build_stop_sign_replay.py."
            )

        for resp in responses:
            records.append(
                {
                    "prompt_hash": ph,
                    "text": resp,
                    "provider": RECORDED_PROVIDER,
                    "model_id": RECORDED_MODEL,
                    "wall_time_ms": RECORDED_WALL_TIME_MS,
                    "usage": dict(RECORDED_USAGE),
                }
            )
    return records


def serialize(records: list[dict[str, Any]]) -> str:
    """Return canonical JSONL text (sorted keys, no whitespace, one record per line)."""
    return (
        "\n".join(
            json.dumps(r, sort_keys=True, separators=(",", ":"))
            for r in records
        )
        + "\n"
    )


def write_fixture(target: Path | None = None) -> Path:
    """Generate the fixture and write it to ``target`` (default: committed path)."""
    out = target if target is not None else FIXTURE_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(serialize(build_records()), encoding="utf-8")
    return out


if __name__ == "__main__":
    path = write_fixture()
    print(f"Wrote {path} ({len(build_records())} records)")
