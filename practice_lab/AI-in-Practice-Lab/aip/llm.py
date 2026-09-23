"""The model client: chat() for text, structured() for validated output.

    from aip import chat, structured, Budget

    text = chat("Summarise in one line:\\n" + doc, tier="SMALL")

    class Ticket(BaseModel):
        category: Literal["billing", "claims"]
        urgency: int = Field(ge=1, le=5)

    t = structured(prompt, schema=Ticket, tier="SMALL")   # -> Ticket

This module is a thin public facade over a small set of cohesive
collaborators, each with exactly one reason to change:

    pricing          is_priced / price_of            -- cost arithmetic
    Usage, Budget    the ledger + spend ceiling      -- accounting
    BudgetRegistry   who receives usage              -- fan-out, no globals
    DiskCache        sqlite persistence              -- response caching
    RetryPolicy      which failures retry, backoff   -- resilience policy
    ProviderClient   one HTTP call                   -- transport
    extract_json     tolerant JSON recovery          -- response parsing
    StructuredExtractor  validate + repair loop      -- output enforcement

``raw_call`` wires the transport, cache, retry policy and registry together;
``chat`` / ``structured`` are conveniences over it. Cross-cutting concerns
(caching, accounting, retries) live behind injectable seams, so the pure logic
can be tested without a network.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from aip.config import (
    FREE_PREFIXES,
    PRICES_PER_MTOK,
    PROVIDER_BASE_URLS,
    PROVIDER_KEY_VARS,
    resolve_model,
    settings,
)

T = TypeVar("T", bound=BaseModel)
Messages = Sequence[dict[str, Any]]

# HTTP statuses worth retrying: rate limits and transient server faults.
RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 529})

# Substrings that mark an *exception* as transient (lowercased match).
RETRYABLE_MARKERS: tuple[str, ...] = (
    "ratelimit", "timeout", "overloaded", "apiconnection",
    "internalserver", "serviceunavailable",
)
# Cap on exponential backoff, in seconds. Full jitter is applied on top.
MAX_BACKOFF_S = 30.0
_BACKOFF_BASE_S = 2.0


# ===========================================================================
# pricing -- pure cost arithmetic, no state
# ===========================================================================
class BudgetExceeded(RuntimeError):
    """Raised when a call would push spend past the configured ceiling."""


def is_priced(model: str) -> bool:
    """Three cases, and conflating them is how a cost meter lies:
    priced (in the table) / genuinely free (ollama, local) / unknown."""
    return model in PRICES_PER_MTOK or model.startswith(FREE_PREFIXES)


def price_of(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000


# ===========================================================================
# ledger -- Usage + Budget, and the registry that fans usage out
# ===========================================================================
@dataclass
class Usage:
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False
    calls: int = 0
    priced: bool = True


@dataclass
class Budget:
    """A spend ceiling with a ledger. Use as a context manager.

        with Budget(limit_usd=0.25, label="lab1") as b:
            for ticket in tickets:
                extract(ticket)
        print(b.report())

    Recording is thread-safe. The ceiling check runs after each record, so a
    call that tips the total over the limit raises immediately.
    """

    limit_usd: float = 1.0
    label: str = "unnamed"
    spent_usd: float = 0.0
    calls: int = 0
    cached_calls: int = 0
    unpriced_calls: int = 0
    unpriced_models: set[str] = field(default_factory=set)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, usage: Usage) -> None:
        with self._lock:
            self.calls += 1
            self.cached_calls += usage.cached
            if not usage.priced:
                self.unpriced_calls += 1
                if usage.model:
                    self.unpriced_models.add(usage.model)
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens
            self.spent_usd += usage.cost_usd
            self.latencies_ms.append(usage.latency_ms)
            exceeded = self.spent_usd > self.limit_usd
        if exceeded:
            raise BudgetExceeded(
                f"[{self.label}] spent ${self.spent_usd:.4f} > limit ${self.limit_usd:.4f} "
                f"after {self.calls} calls. Raise the limit deliberately, or find out "
                f"why the loop costs more than you expected."
            )

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        xs = sorted(self.latencies_ms)
        return xs[min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1))))]

    def report(self) -> str:
        hit_rate = (self.cached_calls / self.calls * 100) if self.calls else 0.0
        cost = f"cost=${self.spent_usd:.4f}"
        if self.unpriced_calls:
            cost += f" + {self.unpriced_calls} UNPRICED ({', '.join(sorted(self.unpriced_models))})"
        return (
            f"[{self.label}] calls={self.calls} (cache hits {hit_rate:.0f}%) "
            f"tokens={self.prompt_tokens}in/{self.completion_tokens}out {cost} "
            f"latency p50={self.percentile(50):.0f}ms p95={self.percentile(95):.0f}ms"
        )

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": round(self.spent_usd, 6),
            "unpriced_calls": self.unpriced_calls,
            "unpriced_models": sorted(self.unpriced_models),
            "latency_p50_ms": round(self.percentile(50), 1),
            "latency_p95_ms": round(self.percentile(95), 1),
        }

    def __enter__(self) -> "Budget":
        BudgetRegistry.active.append(self)
        return self
    def __exit__(self, *exc) -> None:
        for i in range(len(BudgetRegistry.active) - 1, -1, -1):
            if BudgetRegistry.active[i] is self:
                del BudgetRegistry.active[i]
                break


class BudgetRegistry:
    """The set of budgets that receive every recorded Usage.

    Replaces the old module-level ``_ACTIVE`` / ``_GLOBAL`` globals with an
    explicit collaborator, so the fan-out is one named concept instead of two
    hidden lists. A process-wide default (the global ceiling) is always
    present; ``Budget`` context managers add themselves on entry.
    """

    active: "list[Budget]" = []

    def __init__(self, default: Budget) -> None:
        self._default = default
        self._lock = threading.Lock()

    def record(self, usage: Usage) -> None:
        with self._lock:
            targets = [self._default, *self.active]
        for budget in targets:
            budget.record(usage)

    def default(self) -> Budget:
        return self._default


_GLOBAL = Budget(limit_usd=settings.budget_usd, label="process-total")
_REGISTRY = BudgetRegistry(_GLOBAL)


def _record(usage: Usage) -> None:
    """Called after every model call: feeds the global and any active budgets."""
    _REGISTRY.record(usage)


def global_budget() -> Budget:
    return _GLOBAL


# ===========================================================================
# disk cache
# ===========================================================================
class CacheMiss(RuntimeError):
    """Raised in offline mode when a request has no cached response."""


class ResponseCache(Protocol):
    """The caching seam. Swap in an in-memory cache for tests."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def put(self, key: str, response: dict[str, Any]) -> None: ...


class DiskCache:
    """A sqlite-backed response cache, keyed by a hash of the request.

    One table, one connection per operation (short-lived; sqlite is cheap here),
    serialised by a process-wide lock. Disabled -- silently a no-op -- when
    ``settings.cache_enabled`` is false, so callers need not branch.
    """

    _SCHEMA = "CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, response TEXT NOT NULL)"

    def __init__(self, path: os.PathLike | str, enabled: bool = True) -> None:
        self._path = path
        self._enabled = enabled
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=30)
        conn.execute(self._SCHEMA)
        return conn

    def get(self, key: str) -> dict[str, Any] | None:
        if not self._enabled:
            return None
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT response FROM calls WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, response: dict[str, Any]) -> None:
        if not self._enabled:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO calls (key, response) VALUES (?, ?)",
                (key, json.dumps(response, default=str)),
            )

    def clear(self) -> int:
        """Drop all cached responses. Returns the number removed."""
        with self._lock, self._connect() as conn:
            return conn.execute("DELETE FROM calls").rowcount


_CACHE = DiskCache(settings.cache_dir / "calls.sqlite3", enabled=settings.cache_enabled)


def clear_cache() -> int:
    """Drop all cached responses. Returns the number removed."""
    return _CACHE.clear()


# ===========================================================================
# transport -- one HTTP call, no caching/retry/accounting
# ===========================================================================
class StructuredOutputError(RuntimeError):
    """The model could not be coerced into a valid instance of the schema."""

    def __init__(self, message: str, raw: str = "", attempts: int = 0):
        super().__init__(message)
        self.raw = raw
        self.attempts = attempts


@dataclass
class Completion:
    """One completion, already priced and timed."""

    text: str
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float = 0.0
    latency_ms: float = 0.0

    def usage(self, model: str, *, cached: bool) -> Usage:
        return Usage(
            model=model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost_usd=0.0 if cached else self.cost_usd,
            latency_ms=0.0 if cached else self.latency_ms,
            cached=cached,
            calls=1,
            priced=True if cached else is_priced(model),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "finish_reason": self.finish_reason,
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "cost_usd": self.cost_usd,
                "latency_ms": self.latency_ms,
                "cached": False,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Completion":
        usage = data["usage"]
        return cls(
            text=data["text"],
            finish_reason=data["finish_reason"],
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            cost_usd=0.0,
            latency_ms=0.0,
        )


class ProviderError(RuntimeError):
    """A transport-level failure. Carries the HTTP status when there is one."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _split_model(model: str) -> tuple[str, str]:
    """'gemini/gemini-2.0-flash' -> ('gemini', 'gemini-2.0-flash')."""
    provider, _, name = model.partition("/")
    return provider, name


class ProviderClient(Protocol):
    """The transport seam: send messages, get a Completion back.

    ``raw_call`` depends on this protocol, not on httpx, so a fake client can
    stand in for tests and no network is required to exercise the retry,
    caching and accounting paths.
    """

    def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> Completion: ...


class OpenAICompatibleClient:
    """One HTTP call to an OpenAI-compatible chat-completions endpoint.

    Stateless: a fresh ``httpx.Client`` per call, so the class holds no
    connection state and needs no lifecycle management.
    """

    def __init__(
        self,
        timeout_s: float,
        retryable_statuses: Iterable[int] = RETRYABLE_STATUSES,
    ) -> None:
        self._timeout_s = timeout_s
        self._retryable = frozenset(retryable_statuses)

    def _headers(self, provider: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key_var = PROVIDER_KEY_VARS.get(provider, "")
        api_key = os.getenv(key_var, "") if key_var else ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> Completion:
        provider, name = _split_model(model)
        base_url = PROVIDER_BASE_URLS.get(provider)
        if base_url is None:
            raise ValueError(
                f"Unknown provider prefix in model {model!r}. "
                f"Known: {sorted(PROVIDER_BASE_URLS)}."
            )

        payload: dict[str, Any] = {
            "model": name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        with httpx.Client(timeout=self._timeout_s) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                headers=self._headers(provider),
                json=payload,
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"HTTP {resp.status_code}: {resp.text[:500]}",
                status=resp.status_code,
            )

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return Completion(
            text=choice["message"].get("content") or "",
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        )


# ===========================================================================
# retry policy -- which failures retry, and how long to wait
# ===========================================================================
class RetryPolicy:
    """Decides whether a failed attempt is transient, and the backoff to use.

    The original code raised ``RuntimeError`` for a bad status and then
    re-detected it by substring-matching the exception text. Here the status
    is carried on ``ProviderError`` and compared directly, so the retry rule
    has one definition instead of two that can drift apart.
    """

    def __init__(
        self,
        max_attempts: int,
        retryable_statuses: Iterable[int] = RETRYABLE_STATUSES,
        retryable_markers: Iterable[str] = RETRYABLE_MARKERS,
    ) -> None:
        self.max_attempts = max(1, max_attempts)
        self._statuses = frozenset(retryable_statuses)
        self._markers = tuple(m.lower() for m in retryable_markers)
        self._rng = random.Random()

    def is_retryable(self, exc: Exception) -> bool:
        status = getattr(exc, "status", None)
        if isinstance(status, int):
            return status in self._statuses
        haystack = f"{type(exc).__name__} {exc}".lower()
        return any(marker in haystack for marker in self._markers)

    def backoff_s(self, attempt: int) -> float:
        """Exponential backoff with full jitter, capped at MAX_BACKOFF_S."""
        return min(MAX_BACKOFF_S, _BACKOFF_BASE_S ** attempt) * self._rng.random()


# ===========================================================================
# request assembly
# ===========================================================================
def _normalise(prompt_or_messages: str | Messages, system: str | None) -> list[dict[str, Any]]:
    if isinstance(prompt_or_messages, str):
        msgs: list[dict[str, Any]] = [{"role": "user", "content": prompt_or_messages}]
    else:
        msgs = [dict(m) for m in prompt_or_messages]
    if system:
        msgs = [{"role": "system", "content": system}, *msgs]
    return msgs


def _request_key(request: dict[str, Any]) -> str:
    """Stable hash of a request, used as the cache key."""
    return hashlib.sha256(
        json.dumps(request, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


# ===========================================================================
# the wired call: cache -> transport (+ retries) -> accounting
# ===========================================================================
def _call_with_retries(
    client: ProviderClient,
    policy: RetryPolicy,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    response_format: dict | None,
) -> Completion:
    """Call the transport, retrying transient failures per ``policy``."""
    for attempt in range(policy.max_attempts):
        t0 = time.perf_counter()
        try:
            completion = client.complete(
                model, messages, temperature, max_tokens, response_format
            )
        except Exception as exc:  # noqa: BLE001 - transport/provider errors
            if not policy.is_retryable(exc) or attempt == policy.max_attempts - 1:
                raise
            time.sleep(policy.backoff_s(attempt))
        else:
            completion.latency_ms = (time.perf_counter() - t0) * 1000
            return completion
    # Unreachable: the loop either returns or raises.
    raise AssertionError("retry loop exited without returning or raising")


def raw_call(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: dict | None = None,
    client: ProviderClient | None = None,
    cache: ResponseCache | None = None,
    retry_policy: RetryPolicy | None = None,
) -> dict[str, Any]:
    """One provider call with cache, retries and cost accounting.

    Returns ``{"text", "usage", "finish_reason"}``. The transport, cache and
    retry policy are injectable so the orchestration can be tested without a
    network; by default they come from module settings.
    """
    client = client or OpenAICompatibleClient(settings.timeout_s)
    cache = cache or _CACHE
    retry_policy = retry_policy or RetryPolicy(settings.max_retries)

    request = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": response_format,
    }
    key = _request_key(request)

    hit = cache.get(key)
    if hit is not None:
        completion = Completion.from_dict(hit)
        _record(completion.usage(model, cached=True))
        return hit

    if settings.offline:
        raise CacheMiss(
            "AIP_OFFLINE=1 and this request is not in the cache. Run once online "
            "to populate the cache, or unset AIP_OFFLINE."
        )

    completion = _call_with_retries(
        client, retry_policy, model, messages, temperature, max_tokens, response_format
    )
    completion.cost_usd = price_of(
        model, completion.prompt_tokens, completion.completion_tokens
    )
    _record(completion.usage(model, cached=False))

    result = completion.as_dict()
    cache.put(key, result)
    return result


# ===========================================================================
# tolerant JSON recovery
# ===========================================================================
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Best-effort JSON recovery: whole string, then fenced blocks, then the
    widest balanced brace span. Models wrap JSON in prose more often than
    their docs admit."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for block in _JSON_BLOCK.findall(text):
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No JSON object found in response: {text[:300]!r}")


# ===========================================================================
# structured output: validate + repair loop
# ===========================================================================
def _schema_instruction(schema: Type[BaseModel]) -> str:
    """The JSON-Schema instruction appended to the system prompt."""
    return (
        "You must reply with a single JSON object and nothing else. "
        "No prose, no markdown fences, no explanation.\n"
        "The object must validate against this JSON Schema:\n"
        f"{json.dumps(schema.model_json_schema(), indent=2)}"
    )


class StructuredExtractor:
    """Turns a free-text prompt into a validated instance of ``schema``.

    Strategy: ask for JSON with the JSON Schema in the prompt, parse tolerantly,
    validate with Pydantic, and on failure send the validation errors back to
    the model for a repair. Truncation is treated separately -- a repair cannot
    fix a half-written object, so the token budget is doubled instead. Every
    attempt is cached and counted, so a repair is not free; measure that
    trade-off. Encapsulating the loop lets ``structured`` stay a two-line entry
    point and keeps the repair policy independently testable.
    """

    def __init__(self, max_repairs: int = 2) -> None:
        self.max_repairs = max_repairs

    def run(
        self,
        prompt_or_messages: str | Messages,
        *,
        schema: Type[T],
        system: str | None = None,
        tier: str = "SMALL",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
    ) -> T:
        resolved = resolve_model(model or tier)
        temp = settings.temperature if temperature is None else temperature

        instruction = _schema_instruction(schema)
        sys_prompt = f"{system}\n\n{instruction}" if system else instruction
        messages = _normalise(prompt_or_messages, sys_prompt)

        response_format: dict | None = {"type": "json_object"}
        if resolved.startswith(("ollama/", "local/")):
            response_format = None

        raw_text = ""
        errors = ""
        budget = max_tokens
        for attempt in range(self.max_repairs + 1):
            last = attempt == self.max_repairs
            try:
                result = raw_call(
                    messages,
                    model=resolved,
                    temperature=temp,
                    max_tokens=budget,
                    response_format=response_format,
                )
            except Exception:
                # A provider that rejects json mode gets one plain retry.
                if response_format is not None and attempt == 0:
                    response_format = None
                    continue
                raise

            raw_text = result["text"]

            # Truncation is not a schema problem: give it room and try again.
            if result.get("finish_reason") == "length" and not last:
                budget *= 2
                continue

            try:
                return schema.model_validate(extract_json(raw_text))
            except (ValidationError, ValueError) as exc:
                errors = str(exc)[:2000]
                if last:
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": raw_text},
                    {"role": "user", "content": (
                        "That output failed validation with these errors:\n"
                        f"{errors}\n\nReturn the corrected JSON object only. Fix exactly "
                        "the fields named above; leave the others unchanged."
                    )},
                ]

        raise StructuredOutputError(
            f"Could not obtain a valid {schema.__name__} after "
            f"{self.max_repairs + 1} attempts. Last validation error: {errors}",
            raw=raw_text,
            attempts=self.max_repairs + 1,
        )


# ===========================================================================
# public API
# ===========================================================================
def chat(
    prompt_or_messages: str | Messages,
    *,
    system: str | None = None,
    tier: str = "MAIN",
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 1024,
    return_full: bool = False,
    **extra: Any,
):
    """Free-text completion. Returns a string, or the full dict if return_full."""
    result = raw_call(
        _normalise(prompt_or_messages, system),
        model=resolve_model(model or tier),
        temperature=settings.temperature if temperature is None else temperature,
        max_tokens=max_tokens,
    )
    return result if return_full else result["text"]


def structured(
    prompt_or_messages: str | Messages,
    *,
    schema: Type[T],
    system: str | None = None,
    tier: str = "SMALL",
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 2048,
    max_repairs: int = 2,
    **extra: Any,
) -> T:
    """Return a validated instance of ``schema``, or raise StructuredOutputError."""
    return StructuredExtractor(max_repairs=max_repairs).run(
        prompt_or_messages,
        schema=schema,
        system=system,
        tier=tier,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
