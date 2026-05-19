"""infereval: inferentialist evaluation of LLMs.

Derive implication frames from an LLM's endorsement verdicts and measure
inferential mastery against analyst-labeled benchmarks (coverage, Cohen's
kappa, Fleiss' kappa) per the methodology of Allen (2026).
"""

__version__ = "0.2.0"

from .frame import DerivedFrame
from .types import Bearer, Implication, Verdict

__all__ = [
    "__version__",
    "Bearer",
    "DerivedFrame",
    "Implication",
    "Verdict",
]
