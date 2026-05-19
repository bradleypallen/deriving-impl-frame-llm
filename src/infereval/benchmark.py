"""Benchmark :math:`\\beta` model and JSON I/O.

A benchmark is, per Definition 4 of revised.tex, a finite set
:math:`\\{(I_1, V_1), \\ldots, (I_n, V_n)\\}` where each :math:`I_i` is an
implication and each :math:`V_i = (v_{i,1}, \\ldots, v_{i,m})` is a tuple of
analyst verdicts. This module defines the Pydantic-validated JSON shape and
provides :meth:`Benchmark.load` / :meth:`Benchmark.dump` for disk I/O.

The runtime conversion to :class:`infereval.types.Implication` lives on
:meth:`BenchmarkItem.to_implication`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .types import Bearer as _RuntimeBearer
from .types import Implication, Verdict

SCHEMA_VERSION: Literal["1.0"] = "1.0"


class BearerModel(BaseModel):
    """JSON shape for a :class:`infereval.types.Bearer`."""

    model_config = ConfigDict(extra="forbid")

    expression: str
    paraphrases: tuple[str, ...] = ()

    def to_runtime(self, bearer_id: str) -> _RuntimeBearer:
        return _RuntimeBearer(
            id=bearer_id, expression=self.expression, paraphrases=self.paraphrases
        )


class AnalystModel(BaseModel):
    """A human analyst :math:`a_j` whose verdicts appear in :math:`V_i`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str | None = None
    notes: str | None = None


class TemplateContextBuilder(BaseModel):
    """A context builder specified by an inline template string.

    The template is a format string with a single ``{expressions}`` placeholder.
    Bearer expressions are joined by ``joiner`` to fill it.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["template"] = "template"
    template: str = "{expressions}"
    joiner: str = " and "


class PluginContextBuilder(BaseModel):
    """A context builder specified by a dotted import path.

    The plugin must resolve to a callable ``(Sequence[str]) -> str`` taking
    bearer expressions and returning the natural-language context.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["plugin"] = "plugin"
    plugin: str  # e.g. "my_pkg.builders:premise_default"


ContextBuilder = Annotated[
    TemplateContextBuilder | PluginContextBuilder,
    Field(discriminator="kind"),
]


class ContextBuilders(BaseModel):
    """Pair of context builders for :math:`\\mathrm{ctx}_\\Gamma` and :math:`\\mathrm{ctx}_\\Delta`."""

    model_config = ConfigDict(extra="forbid")

    premise: ContextBuilder = Field(
        default_factory=lambda: TemplateContextBuilder(joiner=" and ")
    )
    conclusion: ContextBuilder = Field(
        default_factory=lambda: TemplateContextBuilder(joiner=" or ")
    )


class VerificationPromptOverride(BaseModel):
    """Optional benchmark-level override of the framework's default verification prompt.

    All four fields are optional in practice (``template`` is required by
    the schema since it is the minimal thing an override needs to
    contribute). When a field is ``None`` the framework default is used:

    - :attr:`system` ``None`` → :data:`infereval.prompts.DEFAULT_SYSTEM_PROMPT`.
    - :attr:`parse_regex` ``None`` → :data:`infereval.prompts.DEFAULT_PARSE_REGEX`.
    - :attr:`id` ``None`` → the caller-supplied ``override_id`` parameter to
      :func:`infereval.prompts.resolve_verification_prompt`.

    Adding the ``system`` field makes the paraphrase-axis experiment
    fully JSON-drivable (no Python required to vary the verification prompt).
    """

    model_config = ConfigDict(extra="forbid")

    template: str
    system: str | None = None
    parse_regex: str | None = None
    id: str | None = None


class RSRTarget(BaseModel):
    """Target inference :math:`\\langle X, A \\rangle` for an RSR-targeted item.

    See revised.tex Remark on "RSR-targeted benchmarks".
    """

    model_config = ConfigDict(extra="forbid")

    X: list[str]
    A: list[str]

    @field_validator("X", "A", mode="before")
    @classmethod
    def _dedup_and_sort(cls, v: object) -> object:
        if isinstance(v, list):
            return sorted({str(x) for x in v})
        return v


class BenchmarkItem(BaseModel):
    """A single benchmark item: an implication paired with analyst verdicts."""

    model_config = ConfigDict(extra="forbid")

    id: str
    premises: list[str]
    conclusions: list[str]
    analyst_verdicts: list[Verdict]
    tags: list[str] = Field(default_factory=list)
    rsr_target: RSRTarget | None = None

    @field_validator("premises", "conclusions", mode="before")
    @classmethod
    def _dedup_and_sort_bearer_ids(cls, v: object) -> object:
        if isinstance(v, list):
            return sorted({str(x) for x in v})
        return v

    @field_serializer("premises", "conclusions")
    def _serialize_sorted(self, value: list[str]) -> list[str]:
        return sorted(value)

    def to_implication(self) -> Implication:
        """Return the runtime :class:`Implication` view of this item."""
        return Implication(
            premises=frozenset(self.premises),
            conclusions=frozenset(self.conclusions),
            id=self.id,
        )


class Benchmark(BaseModel):
    """A benchmark :math:`\\beta` over a bearer set, analyst panel, and items.

    See revised.tex Definition 4.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    id: str
    title: str | None = None
    domain: str | None = None
    description: str | None = None
    bearers: dict[str, BearerModel]
    analysts: list[AnalystModel] = Field(min_length=1)
    context_builders: ContextBuilders = Field(default_factory=ContextBuilders)
    verification_prompt: VerificationPromptOverride | None = None
    items: list[BenchmarkItem]

    @model_validator(mode="after")
    def _check_consistency(self) -> Benchmark:
        # Analyst ids unique
        analyst_ids = [a.id for a in self.analysts]
        if len(analyst_ids) != len(set(analyst_ids)):
            raise ValueError("Analyst ids must be unique")

        # Bearer ids consistent: every premise / conclusion / rsr_target id must
        # appear in self.bearers
        bearer_keys = set(self.bearers)
        item_ids: set[str] = set()
        for item in self.items:
            if item.id in item_ids:
                raise ValueError(f"Duplicate item id: {item.id!r}")
            item_ids.add(item.id)

            unknown_premise = set(item.premises) - bearer_keys
            unknown_concl = set(item.conclusions) - bearer_keys
            if unknown_premise or unknown_concl:
                raise ValueError(
                    f"Item {item.id!r} references unknown bearer ids: "
                    f"premises={sorted(unknown_premise)}, conclusions={sorted(unknown_concl)}"
                )
            if item.rsr_target is not None:
                unknown_rsr = (
                    set(item.rsr_target.X) | set(item.rsr_target.A)
                ) - bearer_keys
                if unknown_rsr:
                    raise ValueError(
                        f"Item {item.id!r} rsr_target references unknown bearer ids: "
                        f"{sorted(unknown_rsr)}"
                    )

            # Analyst-verdict tuple length must equal m
            if len(item.analyst_verdicts) != len(self.analysts):
                raise ValueError(
                    f"Item {item.id!r} has {len(item.analyst_verdicts)} analyst verdicts "
                    f"but the benchmark declares {len(self.analysts)} analysts"
                )

        return self

    @property
    def m(self) -> int:
        """Number of analysts :math:`m`."""
        return len(self.analysts)

    @property
    def n(self) -> int:
        """Number of items :math:`n`."""
        return len(self.items)

    def bearer(self, bearer_id: str) -> _RuntimeBearer:
        """Runtime :class:`Bearer` for ``bearer_id``."""
        return self.bearers[bearer_id].to_runtime(bearer_id)

    def runtime_bearers(self) -> dict[str, _RuntimeBearer]:
        """All bearers as runtime :class:`Bearer` instances, keyed by id."""
        return {bid: bm.to_runtime(bid) for bid, bm in self.bearers.items()}

    def analyst_index(self, analyst_id: str) -> int:
        """0-based index of analyst ``analyst_id`` within :attr:`analysts`."""
        for j, a in enumerate(self.analysts):
            if a.id == analyst_id:
                return j
        raise KeyError(f"No analyst with id {analyst_id!r}")

    @classmethod
    def load(cls, path: str | Path) -> Benchmark:
        """Load a benchmark from JSON on disk and validate."""
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    @classmethod
    def loads(cls, text: str) -> Benchmark:
        """Load a benchmark from a JSON string and validate."""
        return cls.model_validate_json(text)

    def dump(self, path: str | Path, *, indent: int = 2) -> None:
        """Write the benchmark to ``path`` as canonical-ish JSON."""
        with Path(path).open("w", encoding="utf-8") as f:
            f.write(self.dumps(indent=indent))
            f.write("\n")

    def dumps(self, *, indent: int = 2) -> str:
        """Return the benchmark as a JSON string."""
        return self.model_dump_json(indent=indent, exclude_none=True)
