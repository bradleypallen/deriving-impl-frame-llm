"""Tests for ``infereval.endorsement.endorse`` against ``ScriptedProvider``."""

from __future__ import annotations

from infereval.context import make_template_builder
from infereval.endorsement import endorse
from infereval.evaluation import EndorsementConfig, ProviderParams
from infereval.prompts import DEFAULT_VERIFICATION_PROMPT
from infereval.providers.mock import ScriptedProvider
from infereval.types import Bearer, Implication, Verdict

# ---- Fixtures shared at module level ----------------------------------------

PREMISE_BUILDER = make_template_builder(joiner=" and ")
CONCLUSION_BUILDER = make_template_builder(joiner=" or ")


def _bearers() -> dict[str, Bearer]:
    return {
        "sa": Bearer(id="sa", expression="$a$ is a stop sign"),
        "ra": Bearer(id="ra", expression="$a$ is red"),
        "n": Bearer(id="n", expression="it is nighttime"),
    }


def _imp(prem: list[str], conc: list[str], iid: str = "row-x") -> Implication:
    return Implication.of(prem, conc, id=iid)


def _config(n_samples: int = 5, tie_break: str = "abstain") -> EndorsementConfig:
    return EndorsementConfig(n_samples=n_samples, tie_break=tie_break)  # type: ignore[arg-type]


def _run(
    provider: ScriptedProvider,
    *,
    n_samples: int = 5,
    tie_break: str = "abstain",
    implication: Implication | None = None,
):
    return endorse(
        implication or _imp(["sa"], ["ra"]),
        _bearers(),
        provider,
        _config(n_samples=n_samples, tie_break=tie_break),
        ProviderParams(),
        premise_builder=PREMISE_BUILDER,
        conclusion_builder=CONCLUSION_BUILDER,
        request_id_prefix="run-1:row-x",
    )


# ---- Clean majority ---------------------------------------------------------


class TestCleanMajority:
    def test_unanimous_good(self) -> None:
        provider = ScriptedProvider(responses=["GOOD"] * 5)
        record = _run(provider)
        assert record.verdict == Verdict.GOOD
        assert not record.tie_broken
        assert record.counts == {Verdict.GOOD: 5, Verdict.BAD: 0, Verdict.ABSTAIN: 0}
        assert len(record.samples) == 5
        assert all(s.parse_status == "ok" for s in record.samples)

    def test_unanimous_bad(self) -> None:
        provider = ScriptedProvider(responses=["BAD"] * 5)
        record = _run(provider)
        assert record.verdict == Verdict.BAD

    def test_clear_majority(self) -> None:
        provider = ScriptedProvider(responses=["GOOD", "GOOD", "GOOD", "BAD", "ABSTAIN"])
        record = _run(provider)
        assert record.verdict == Verdict.GOOD
        assert record.counts[Verdict.GOOD] == 3
        assert record.counts[Verdict.BAD] == 1
        assert record.counts[Verdict.ABSTAIN] == 1


# ---- Ties ------------------------------------------------------------------


class TestTies:
    def test_pure_good_bad_tie_defaults_to_abstain(self) -> None:
        provider = ScriptedProvider(responses=["GOOD", "GOOD", "BAD", "BAD"])
        record = _run(provider, n_samples=4)
        assert record.verdict == Verdict.ABSTAIN
        assert record.tie_broken

    def test_pure_good_bad_tie_with_explicit_good_winner(self) -> None:
        provider = ScriptedProvider(responses=["GOOD", "GOOD", "BAD", "BAD"])
        record = _run(provider, n_samples=4, tie_break="good")
        assert record.verdict == Verdict.GOOD
        assert record.tie_broken

    def test_tie_with_abstain_in_set_picks_abstain(self) -> None:
        # 2 good, 2 abstain -- abstain in tied set, always wins
        provider = ScriptedProvider(responses=["GOOD", "GOOD", "ABSTAIN", "ABSTAIN"])
        record = _run(provider, n_samples=4, tie_break="good")
        assert record.verdict == Verdict.ABSTAIN
        assert record.tie_broken


# ---- Unparseable handling --------------------------------------------------


class TestUnparseable:
    def test_all_unparseable_yields_abstain(self) -> None:
        provider = ScriptedProvider(responses=["Hmm...", "Not sure", "...", "?", "??"])
        record = _run(provider)
        assert record.verdict == Verdict.ABSTAIN
        assert record.counts[Verdict.ABSTAIN] == 5
        assert all(s.parse_status == "unparseable" for s in record.samples)

    def test_mixed_parseable_unparseable(self) -> None:
        provider = ScriptedProvider(
            responses=["GOOD", "GOOD", "Not sure", "GOOD", "?"]
        )
        record = _run(provider)
        assert record.verdict == Verdict.GOOD
        assert record.counts[Verdict.GOOD] == 3
        assert record.counts[Verdict.ABSTAIN] == 2
        ok = [s for s in record.samples if s.parse_status == "ok"]
        unparseable = [s for s in record.samples if s.parse_status == "unparseable"]
        assert len(ok) == 3
        assert len(unparseable) == 2

    def test_response_with_extra_prose_still_parses(self) -> None:
        provider = ScriptedProvider(
            responses=[
                "GOOD. The redness of the stop sign persists.",
                "GOOD, given typical stop signs.",
                "Verdict: BAD because painted blue.",
                "GOOD",
                "GOOD",
            ]
        )
        record = _run(provider)
        assert record.verdict == Verdict.GOOD
        assert record.counts[Verdict.GOOD] == 4
        assert record.counts[Verdict.BAD] == 1


# ---- Prompt construction & TeX stripping -----------------------------------


class TestPromptConstruction:
    def test_premise_context_is_tex_stripped(self) -> None:
        provider = ScriptedProvider(responses=["GOOD"] * 3)
        record = _run(provider, n_samples=3, implication=_imp(["sa", "n"], ["ra"]))
        # "$a$" -> "a"
        assert "$" not in record.premise_context
        assert "a is a stop sign" in record.premise_context
        assert "it is nighttime" in record.premise_context

    def test_conclusion_context_is_tex_stripped(self) -> None:
        provider = ScriptedProvider(responses=["GOOD"] * 3)
        record = _run(provider, n_samples=3)
        assert "$" not in record.conclusion_context
        assert "a is red" in record.conclusion_context

    def test_rendered_user_prompt_contains_both(self) -> None:
        provider = ScriptedProvider(responses=["GOOD"] * 3)
        record = _run(provider, n_samples=3)
        assert "Premises:" in record.rendered_user_prompt
        assert "Conclusion:" in record.rendered_user_prompt
        assert record.rendered_user_prompt.endswith("Verdict:")

    def test_strip_tex_can_be_disabled(self) -> None:
        provider = ScriptedProvider(responses=["GOOD"] * 3)
        record = endorse(
            _imp(["sa"], ["ra"]),
            _bearers(),
            provider,
            _config(n_samples=3),
            ProviderParams(),
            premise_builder=PREMISE_BUILDER,
            conclusion_builder=CONCLUSION_BUILDER,
            strip_tex=False,
        )
        assert "$a$" in record.premise_context


# ---- Sample request shape --------------------------------------------------


class _CapturingProvider:
    """A provider that records each SampleRequest it receives."""

    name = "capture"
    model_id = "capture-v1"

    def __init__(self, scripted_text: str = "GOOD") -> None:
        self.requests = []
        self._scripted = scripted_text

    def sample(self, req):  # type: ignore[no-untyped-def]
        from infereval.providers.base import SampleResult

        self.requests.append(req)
        return SampleResult(
            text=self._scripted,
            provider=self.name,
            model_id=self.model_id,
            request_id=req.request_id,
        )


class TestSampleRequestShape:
    def test_n_samples_requests_issued(self) -> None:
        p = _CapturingProvider()
        endorse(
            _imp(["sa"], ["ra"]),
            _bearers(),
            p,  # type: ignore[arg-type]
            _config(n_samples=4),
            ProviderParams(temperature=0.5, max_tokens=10),
            premise_builder=PREMISE_BUILDER,
            conclusion_builder=CONCLUSION_BUILDER,
        )
        assert len(p.requests) == 4

    def test_params_propagated_to_sample_request(self) -> None:
        p = _CapturingProvider()
        endorse(
            _imp(["sa"], ["ra"]),
            _bearers(),
            p,  # type: ignore[arg-type]
            _config(n_samples=2),
            ProviderParams(temperature=0.7, max_tokens=16, top_p=0.9, seed=42),
            premise_builder=PREMISE_BUILDER,
            conclusion_builder=CONCLUSION_BUILDER,
        )
        first = p.requests[0]
        assert first.temperature == 0.7
        assert first.max_tokens == 16
        assert first.top_p == 0.9
        assert first.seed == 42
        assert first.system == DEFAULT_VERIFICATION_PROMPT.system

    def test_request_ids_use_prefix_and_index(self) -> None:
        p = _CapturingProvider()
        endorse(
            _imp(["sa"], ["ra"]),
            _bearers(),
            p,  # type: ignore[arg-type]
            _config(n_samples=3),
            ProviderParams(),
            premise_builder=PREMISE_BUILDER,
            conclusion_builder=CONCLUSION_BUILDER,
            request_id_prefix="run-abc:row-0",
        )
        ids = [req.request_id for req in p.requests]
        assert ids == ["run-abc:row-0:sample-0", "run-abc:row-0:sample-1", "run-abc:row-0:sample-2"]


# ---- Sample failure handling ----------------------------------------------


class _AlwaysFailsProvider:
    name = "always-fails"
    model_id = "fail-v1"

    def sample(self, req):  # type: ignore[no-untyped-def]
        from infereval.providers.base import ProviderSampleError

        raise ProviderSampleError("simulated permanent failure")


class TestSampleFailures:
    def test_provider_failure_yields_abstain_record(self) -> None:
        p = _AlwaysFailsProvider()
        record = _run(p, n_samples=3)  # type: ignore[arg-type]
        assert record.verdict == Verdict.ABSTAIN
        assert all(s.parse_status == "sample_failed" for s in record.samples)
        assert record.counts[Verdict.ABSTAIN] == 3


# ---- Budget-clipped detection --------------------------------------------


class _BudgetClippedProvider:
    """Returns empty text with finish_reason='length' on every call.

    Models reasoning-capable backends that consume budget on silent
    internal reasoning before emitting any verdict tokens (DeepSeek
    v4-flash at max_tokens=32 is the canonical case).
    """

    name = "budget-clipped-mock"
    model_id = "mock-v1"

    def sample(self, req):  # type: ignore[no-untyped-def]
        from infereval.providers.base import SampleResult

        return SampleResult(
            text="",
            provider=self.name,
            model_id=self.model_id,
            request_id=req.request_id,
            finish_reason="length",
            reasoning_tokens=req.max_tokens,
        )


class _MaxTokensProvider(_BudgetClippedProvider):
    """Like _BudgetClippedProvider but using Anthropic's 'max_tokens' value."""

    def sample(self, req):  # type: ignore[no-untyped-def]
        from infereval.providers.base import SampleResult

        return SampleResult(
            text="",
            provider=self.name,
            model_id=self.model_id,
            request_id=req.request_id,
            finish_reason="max_tokens",
            reasoning_tokens=None,
        )


class TestBudgetClipped:
    def test_length_finish_reason_promotes_unparseable_to_budget_clipped(self) -> None:
        record = _run(_BudgetClippedProvider(), n_samples=3)  # type: ignore[arg-type]
        # Verdict still abstain (Definition 2 fallback) ...
        assert record.verdict == Verdict.ABSTAIN
        # ... but parse_status is the diagnostic 'budget_clipped', not 'unparseable'.
        assert all(s.parse_status == "budget_clipped" for s in record.samples)
        assert all(s.parsed_verdict == Verdict.ABSTAIN for s in record.samples)
        # finish_reason and reasoning_tokens propagated onto the record.
        assert all(s.finish_reason == "length" for s in record.samples)
        assert all(s.reasoning_tokens == 1024 for s in record.samples)

    def test_anthropic_max_tokens_finish_reason_promotes(self) -> None:
        record = _run(_MaxTokensProvider(), n_samples=2)  # type: ignore[arg-type]
        assert all(s.parse_status == "budget_clipped" for s in record.samples)
        assert all(s.finish_reason == "max_tokens" for s in record.samples)

    def test_stop_finish_reason_with_parseable_text_stays_ok(self) -> None:
        from infereval.providers.base import SampleResult

        class _OkProvider:
            name = "ok-mock"
            model_id = "ok-v1"

            def sample(self, req):  # type: ignore[no-untyped-def]
                return SampleResult(
                    text="GOOD",
                    provider=self.name,
                    model_id=self.model_id,
                    request_id=req.request_id,
                    finish_reason="stop",
                )

        record = _run(_OkProvider(), n_samples=1)  # type: ignore[arg-type]
        assert record.samples[0].parse_status == "ok"
        assert record.samples[0].finish_reason == "stop"

    def test_unparseable_without_budget_finish_reason_stays_unparseable(self) -> None:
        # Model produced parseable-looking text that just didn't contain a verdict
        # token, with a clean stop reason: that's a genuine unparseable, not budget.
        from infereval.providers.base import SampleResult

        class _UnparseableButCleanProvider:
            name = "u-mock"
            model_id = "u-v1"

            def sample(self, req):  # type: ignore[no-untyped-def]
                return SampleResult(
                    text="I am not sure about this one.",
                    provider=self.name,
                    model_id=self.model_id,
                    request_id=req.request_id,
                    finish_reason="stop",
                )

        record = _run(_UnparseableButCleanProvider(), n_samples=1)  # type: ignore[arg-type]
        assert record.samples[0].parse_status == "unparseable"
