"""Stage-1 tests for the v0.6.1 IdentityCriterion / ReliabilityClaim
declaration on the claims-file model.

Covers:
- ``IdentityCriterion`` field-level validation (required fields, types,
  defaults on the framework-substantiated booleans).
- ``ReliabilityClaim`` JSON round-trip.
- ``ConstructValidityClaims.reliability`` is optional at the top level
  so pre-v0.6.1 claims files (without the block) still validate.
- ``ConstructValidityClaims.stub()`` includes the new block with
  placeholder values and the framework-substantiated booleans defaulted
  to True (the analyst denies them only by also choosing not to retest).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from infereval.report import (
    CompetingExplanationChecks,
    ConstructValidityClaims,
    IdentityCriterion,
    ReliabilityClaim,
)


def _valid_criterion() -> IdentityCriterion:
    return IdentityCriterion(
        same_provider_model_id=True,
        cross_update_identity_asserted=True,
        same_scaffolding=True,
        unverifiable_caveats="OpenAI snapshot fingerprint stable across runs.",
        rationale="Two runs minutes apart on the same provider snapshot.",
    )


# ---- IdentityCriterion field-level validation ----------------------------


def test_identity_criterion_requires_analyst_substantiated_booleans() -> None:
    # All three analyst-substantiated booleans are required (no defaults).
    with pytest.raises(ValidationError):
        IdentityCriterion(  # type: ignore[call-arg]
            unverifiable_caveats="x",
            rationale="x",
        )


def test_identity_criterion_requires_caveats_and_rationale_text() -> None:
    with pytest.raises(ValidationError):
        IdentityCriterion(  # type: ignore[call-arg]
            same_provider_model_id=True,
            cross_update_identity_asserted=True,
            same_scaffolding=True,
        )


def test_identity_criterion_framework_substantiated_booleans_default_true() -> None:
    c = _valid_criterion()
    assert c.same_benchmark_hash is True
    assert c.same_endorsement_config is True
    assert c.same_paraphrase_variant is True


def test_identity_criterion_rejects_unknown_fields() -> None:
    """extra='forbid' protects the schema from accidental drift."""
    with pytest.raises(ValidationError):
        IdentityCriterion.model_validate(
            {
                "same_provider_model_id": True,
                "cross_update_identity_asserted": True,
                "same_scaffolding": True,
                "unverifiable_caveats": "x",
                "rationale": "x",
                "unknown_field": True,
            }
        )


def test_identity_criterion_round_trips_through_json() -> None:
    c = _valid_criterion()
    payload = c.model_dump_json()
    restored = IdentityCriterion.model_validate_json(payload)
    assert restored == c


# ---- ReliabilityClaim -----------------------------------------------------


def test_reliability_claim_wraps_identity_criterion() -> None:
    r = ReliabilityClaim(identity_criterion=_valid_criterion())
    assert r.identity_criterion.same_provider_model_id is True


def test_reliability_claim_round_trips_through_json() -> None:
    r = ReliabilityClaim(identity_criterion=_valid_criterion())
    restored = ReliabilityClaim.model_validate_json(r.model_dump_json())
    assert restored == r


# ---- ConstructValidityClaims integration ---------------------------------


def _minimal_claims_dict() -> dict:
    """Pre-v0.6.1 claims-file shape (no reliability block)."""
    return {
        "mastery_sense": {"sense": "evaluative", "description": "x"},
        "scope": {"scope": "items_in_benchmark", "justification": "x"},
        "constitution": {
            "position": "evidence_of_mastery",
            "justification": "x",
        },
        "carving": {"acknowledges_carving_indexed": False, "notes": ""},
        "competing_explanations": {},
    }


def test_pre_v0_6_1_claims_files_still_validate() -> None:
    """Backward-compat: a claims file written under v0.6.0 (no
    reliability block) must still validate against the v0.6.1 model."""
    claims = ConstructValidityClaims.model_validate(_minimal_claims_dict())
    assert claims.reliability is None


def test_v0_6_1_claims_file_with_reliability_validates() -> None:
    payload = _minimal_claims_dict()
    payload["reliability"] = {
        "identity_criterion": _valid_criterion().model_dump()
    }
    claims = ConstructValidityClaims.model_validate(payload)
    assert claims.reliability is not None
    assert claims.reliability.identity_criterion.same_provider_model_id is True


def test_construct_validity_claims_rejects_unknown_top_level_fields() -> None:
    payload = _minimal_claims_dict()
    payload["unknown_block"] = {}
    with pytest.raises(ValidationError):
        ConstructValidityClaims.model_validate(payload)


# ---- stub() -------------------------------------------------------------


def test_stub_includes_reliability_block() -> None:
    stub = ConstructValidityClaims.stub()
    assert stub.reliability is not None
    crit = stub.reliability.identity_criterion
    # Framework-substantiated: stub asserts them by default.
    assert crit.same_benchmark_hash is True
    assert crit.same_endorsement_config is True
    assert crit.same_paraphrase_variant is True
    # Analyst-substantiated: stub leaves False so the analyst has to
    # consciously assert each one. The verdict gate at scope >=
    # domain_D_as_sampled will catch the case where the analyst
    # leaves them False and doesn't fill in the rationale.
    assert crit.same_provider_model_id is False
    assert crit.cross_update_identity_asserted is False
    assert crit.same_scaffolding is False
    # Free-text fields contain FILL IN placeholders.
    assert "FILL IN" in crit.unverifiable_caveats
    assert "FILL IN" in crit.rationale


def test_stub_serializes_and_validates_round_trip() -> None:
    """The stub must be a structurally valid claims file straight out
    of init-claims — even though the FILL IN placeholders make it
    semantically incomplete, the framework should be able to load it
    back without parse errors."""
    stub = ConstructValidityClaims.stub()
    json_str = stub.model_dump_json(indent=2)
    restored = ConstructValidityClaims.model_validate(json.loads(json_str))
    assert restored == stub


def test_stub_existing_blocks_unchanged() -> None:
    """Regression guard: the existing R16/R17/R18/R19 stubs must not
    drift when the new R22 block is added."""
    stub = ConstructValidityClaims.stub()
    assert stub.mastery_sense.sense == "evaluative"
    assert stub.scope.scope == "items_in_benchmark"
    assert stub.constitution.position == "evidence_of_mastery"
    assert stub.carving.acknowledges_carving_indexed is False
    assert stub.competing_explanations == CompetingExplanationChecks()
