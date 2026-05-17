# Providers

The framework supports four providers out of the box: **Anthropic**, **OpenAI**, **OpenRouter**, and **mock** (`ScriptedProvider` for tests, `ReplayProvider` for deterministic replay against a JSONL fixture).

This page is the operational reference for the three real providers — credentials, model id conventions, and the per-provider quirks that have actually bitten us.

## Quick reference

| Provider | API key env var | `pip install` extras | Best for |
|---|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | `infereval[anthropic]` | Claude models (Opus, Sonnet, Haiku families). Messages API. |
| `openai` | `OPENAI_API_KEY` | `infereval[openai]` | OpenAI models. Chat Completions API. |
| `openrouter` | `OPENROUTER_API_KEY` | `infereval[openai]` (shared SDK) | DeepSeek, Mistral, Llama, Qwen, and any other model OpenRouter aggregates. Also Anthropic / OpenAI models if you want a unified billing flow. |
| `mock` | — | (always present) | Tests; the `--replay-from` flow for deterministic CI / demo runs. |

## Anthropic

```
pip install 'infereval[anthropic]'
export ANTHROPIC_API_KEY=sk-ant-...
infereval evaluate bench.json \
    --provider anthropic \
    --model claude-haiku-4-5-20251001 \
    --output eta.json --n-samples 5 --log run.jsonl
```

Model id conventions (as of 2026-05): `claude-haiku-4-5-20251001`, `claude-sonnet-4-5-20250929`, `claude-opus-4-5-20251101`, plus dated variants. The shorter aliases (`claude-haiku-4-5`, `claude-sonnet-4-5`, etc.) also work and point at the latest version of each model line.

### Quirks

- **`seed` is ignored.** Anthropic's Messages API does not honor a `seed` parameter. If you supply one, the framework records it in `Evaluation.model.params.seed` (so you can see what was requested) and emits a one-time warning on the `infereval.providers.anthropic` logger: `provider.anthropic.seed_ignored`. The seed has no effect on the model's output. Use `temperature=0.0` for the closest approximation of determinism Anthropic supports.
- **`stop` sequences** are passed through as `stop_sequences=[...]`. The default-v1 verification prompt doesn't need them.
- **Per-call cost is small** for typical evaluations: each sample is ~80 input tokens + ~6 output tokens. A 4-item × 5-sample run is ~$0.001 on Haiku.

### Recommended defaults

```python
EndorsementConfig(n_samples=5)
ProviderParams(temperature=0.0, max_tokens=32)
```

Haiku and Sonnet handle the `default-v1` prompt fine at `max_tokens=32`. If you swap to a verification prompt that asks for reasoning, raise `max_tokens` accordingly.

## OpenAI

```
pip install 'infereval[openai]'
export OPENAI_API_KEY=sk-...
infereval evaluate bench.json \
    --provider openai \
    --model gpt-4.1 \
    --output eta.json --n-samples 5 --log run.jsonl
```

Model id conventions: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-5`, `gpt-5-mini`, etc., plus dated variants (`gpt-4.1-2025-04-14`, …). Reasoning-family models (`o1`, `o3`, `o4-mini`) work but consume tokens silently — see the reasoning-tokens caveat below.

### Quirks

- **`seed` is honored** for most chat-completion models. Passes through as-is. Reproducibility under fixed `seed + temperature` is the best you'll get from any provider.
- **API surface choice**: the framework uses Chat Completions, not the newer Responses API. This was a deliberate decision to maximize OpenRouter compatibility (Chat Completions is the shared interface). If you need Responses-API-specific features (e.g. structured outputs with strict schemas), drop to the OpenAI SDK directly and pass a `client=` kwarg to `OpenAIProvider`.
- **Reasoning models** (`o1`, `o3`, `o4-mini`, ...) use internal reasoning tokens that consume the `max_tokens` budget invisibly. See the OpenRouter section below for the canonical case (DeepSeek v4-flash); the OpenAI reasoning models exhibit the same behavior. Raise `max_tokens` to 512+ for these.

### Recommended defaults

```python
# Non-reasoning models (gpt-4.1 family, gpt-5 family, gpt-4o family):
EndorsementConfig(n_samples=5)
ProviderParams(temperature=0.0, max_tokens=32, seed=42)

# Reasoning-family models (o1, o3, o4-mini):
ProviderParams(temperature=0.0, max_tokens=2048, seed=42)
```

## OpenRouter

```
pip install 'infereval[openai]'   # shared SDK with OpenAI
export OPENROUTER_API_KEY=sk-or-...
infereval evaluate bench.json \
    --provider openrouter \
    --model deepseek/deepseek-v4-flash \
    --output eta.json --n-samples 5 --max-tokens 512 --log run.jsonl \
    --http-referer https://github.com/your-org/your-repo \
    --x-title your-experiment-name
```

OpenRouter is OpenAI-API-compatible at the protocol level; the framework uses the OpenAI SDK with `base_url="https://openrouter.ai/api/v1"` and the OpenRouter API key. Any of the hundreds of models OpenRouter aggregates is reachable through this single provider.

Model id conventions: `<vendor>/<model>` (`anthropic/claude-3.5-sonnet`, `openai/gpt-4o-mini`, `deepseek/deepseek-v4-flash`, `meta-llama/llama-3.3-70b-instruct`, `qwen/qwen-2.5-72b-instruct`, ...).

### Quirks

- **Attribution headers** (`HTTP-Referer`, `X-Title`) are recommended for accountability and show up in your OpenRouter dashboard. The framework supports them as `--http-referer` and `--x-title` flags (or `http_referer=`, `x_title=` kwargs in the Python API).
- **The API key env var is `OPENROUTER_API_KEY`**, *not* `OPENAI_API_KEY`. The framework explicitly does not fall back to the OpenAI key (and a test enforces this), so you can have both set without cross-contamination.
- **DeepSeek v4-flash uses silent reasoning tokens.** This is the canonical reasoning-tokens case. At the framework default `max_tokens=32`, the model returns `content=None`, `finish_reason="length"`, and `reasoning_tokens=32`. The framework correctly maps this to `Verdict.ABSTAIN` with `parse_status="unparseable"`, but the abstain is a "budget exhausted" abstain, not a "model declined" abstain — see [issue #4](https://github.com/bradleypallen/deriving-impl-frame-llm/issues/4). **Always pass `--max-tokens 512` or higher** when targeting DeepSeek v4-flash and similar models. The same applies to `qwen-qwq-*`, `openai/o1-*`, and other reasoning-flavored models on OpenRouter.
- **Per-model pricing varies enormously.** Check the OpenRouter model page before launching a large benchmark. `deepseek/deepseek-v4-flash` is cheap (~$0.10 per million input tokens); `openai/o3` is not.

### Recommended defaults

```python
# Non-reasoning models (anthropic/claude-*, openai/gpt-4o-mini, ...):
ProviderParams(temperature=0.0, max_tokens=32)

# Reasoning models (deepseek/*, anything with -r1 or o1/o3 in the name):
ProviderParams(temperature=0.0, max_tokens=512)
```

### Listing currently available DeepSeek models

```bash
curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    https://openrouter.ai/api/v1/models | jq '.data[] | select(.id|test("deepseek")) | .id'
```

The same trick works for any other vendor: replace `deepseek` with `anthropic`, `meta-llama`, etc.

## Mock providers (testing / replay)

Two flavors live in `infereval.providers.mock`:

### `ScriptedProvider`

```python
from infereval.providers.mock import ScriptedProvider
from infereval.providers.base import SampleRequest

p = ScriptedProvider(responses=["GOOD", "GOOD", "BAD"])
p.sample(SampleRequest(prompt="anything"))  # -> SampleResult(text="GOOD", ...)
```

Cycles through `responses` indefinitely. Useful for unit tests that need to control what the "model" says without hitting an API.

### `ReplayProvider`

```python
from infereval.providers.mock import ReplayProvider

p = ReplayProvider("tests/fixtures/stop_sign_replay.jsonl")
```

Loads a JSONL fixture where each record carries a `prompt_hash` (SHA-256 of the user prompt) and a `text` field. When `sample()` is called, the prompt is hashed, the matching record (or next record sharing that hash) is returned. Missing prompt → clear `ProviderSampleError` with a diagnostic message.

The CLI exposes this as `--replay-from <path>`. It's the basis of the 60-second quickstart in the README and is the right tool for any deterministic CI / demo run.

Fixture format:

```jsonl
{"prompt_hash":"sha256:...","text":"GOOD","provider":"anthropic","model_id":"claude-haiku-4-5-20251001","wall_time_ms":120.0,"usage":{"input_tokens":60,"output_tokens":6}}
```

To author a fixture from real provider runs, the pattern is:

1. Run `infereval evaluate ... --log run.jsonl` against the real provider.
2. Process `run.jsonl` to extract one record per `sample.completed` event into the replay format.

A helper to do step 2 cleanly is on the roadmap (issue not yet open); for now `tests/fixtures/build_stop_sign_replay.py` is the canonical example.

## A common-issue checklist

| Symptom | Likely cause | Fix |
|---|---|---|
| Coverage near zero, lots of `parse_status: unparseable` with empty `raw_response` | `max_tokens` too low for a reasoning-capable model | Raise `--max-tokens` to 256+ |
| `ProviderConfigError: ANTHROPIC_API_KEY not set` despite `export ANTHROPIC_API_KEY=...` in `~/.bashrc` | Shell didn't re-source profile | `source ~/.bashrc` or open a new terminal; verify with `echo $ANTHROPIC_API_KEY \| head -c 8` |
| `ProviderConfigError: anthropic SDK not installed` | `infereval` installed without provider extras | `pip install 'infereval[anthropic]'` (or `[openai]` / `[all]`) |
| `provider.anthropic.seed_ignored` warning on every Anthropic run | Anthropic doesn't honor seed | Expected; either drop `seed` or accept the warning |
| `ProviderSampleError: no recorded response for prompt_hash=...` from `ReplayProvider` | Verification prompt template, bearer expressions, or context builders have changed since the fixture was generated | Regenerate the fixture (`python -m tests.fixtures.build_stop_sign_replay`) or use a real provider for new prompts |
| First sample on a long evaluation takes minutes | Anthropic / OpenAI / OpenRouter latency spike on a specific prompt; the BaseProvider retry loop is sleeping with exponential backoff | Wait it out (the retry policy caps at 4 attempts), or interrupt and inspect the partial JSONL log to confirm what happened |
| OpenRouter dashboard shows no app attribution | Missing `--http-referer` / `--x-title` | Pass both flags |

## Adding a new provider

If you want to wire up a new backend (Cohere, Together, Replicate, a self-hosted endpoint, ...), the pattern is:

1. Subclass `infereval.providers.base.BaseProvider`.
2. Set `name = "your-name"` as a class attribute.
3. Implement `_sample_once(self, req: SampleRequest) -> SampleResult` — one provider call, no retries (the base class handles them).
4. Implement `_is_transient(self, exc: Exception) -> bool` — return `True` for errors the retry loop should re-try.
5. Register in `infereval.providers.__init__.get_provider`.

The Anthropic / OpenAI implementations are ~150 lines each and serve as templates. If you write one, please open a PR.
