"""Dependency-light tool contracts, behavior hints, and visibility policy."""

from __future__ import annotations

import fnmatch
import functools
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

VALID_TOOL_PROFILES = frozenset({"full", "readonly", "market", "account", "core", "custom"})
OAUTH_BASE_SCOPE = "qmt:read"
OAUTH_MARKET_SCOPE = "qmt:market"
OAUTH_ACCOUNT_SCOPE = "qmt:account"
OAUTH_MANAGE_SCOPE = "qmt:manage"
OAUTH_ADMIN_SCOPE = "qmt:admin"

MUTATION_TOOL_PATTERNS = (
    "qmt_xtdata_quote_subscribe",
    "qmt_xtdata_quote_unsubscribe",
    "qmt_xtdata_download_*",
    "qmt_xtdata_refresh_*",
    "qmt_xtdata_sector_create*",
    "qmt_xtdata_sector_add_codes",
    "qmt_xtdata_sector_remove_codes",
    "qmt_xtdata_sector_delete",
    "qmt_xtdata_sector_reset",
    "qmt_xtdata_formula_generate_factor",
    "qmt_xtdata_formula_subscribe",
    "qmt_xtdata_formula_unsubscribe",
)


@dataclass(frozen=True)
class ToolBehavior:
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = True


@dataclass(frozen=True)
class ToolVisibilityPolicy:
    profile: str = "full"
    allowlist: tuple[str, ...] = ()
    denylist: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = self.profile.strip().lower()
        object.__setattr__(self, "profile", normalized)
        if normalized not in VALID_TOOL_PROFILES:
            raise ValueError(
                f"invalid tool profile {self.profile!r}; expected one of {', '.join(sorted(VALID_TOOL_PROFILES))}"
            )
        if normalized == "custom" and not self.allowlist:
            raise ValueError("custom tool profile requires a non-empty allowlist")

    def visible(self, *, name: str, family: str, read_only: bool) -> bool:
        if family == "core":
            return True

        selected = {
            "full": True,
            "readonly": read_only,
            "market": family == "xtdata",
            "account": family in {"xttrade_query", "portfolio"},
            "core": False,
            "custom": True,
        }[self.profile]
        if not selected:
            return False
        if self.allowlist and not self._matches(name, self.allowlist):
            return False
        return not self._matches(name, self.denylist)

    @staticmethod
    def _matches(name: str, patterns: tuple[str, ...]) -> bool:
        return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def required_oauth_scopes(*, family: str, read_only: bool) -> tuple[str, ...]:
    scopes = [OAUTH_BASE_SCOPE]
    if family == "xtdata":
        scopes.append(OAUTH_MARKET_SCOPE)
    elif family in {"xttrade_query", "portfolio"}:
        scopes.append(OAUTH_ACCOUNT_SCOPE)
    if not read_only:
        scopes.append(OAUTH_MANAGE_SCOPE)
    return tuple(scopes)


def oauth_scopes_allow(required: tuple[str, ...], granted: set[str] | frozenset[str]) -> bool:
    if OAUTH_BASE_SCOPE not in granted:
        return False
    return OAUTH_ADMIN_SCOPE in granted or set(required) <= granted


def default_tool_title(name: str) -> str:
    words = []
    for word in name.split("_"):
        if word in {"qmt", "mcp"}:
            words.append(word.upper())
        elif word in {"xtdata", "xttrade"}:
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words)


def mutation_like(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in MUTATION_TOOL_PATTERNS)


def register_mcp_tool(
    mcp: Any,
    *,
    wrapped: Callable[..., Any],
    name: str,
    title: str,
    description: str,
    behavior: ToolBehavior,
    resource_uri: str | None = None,
    app_visibility: tuple[str, ...] = ("model", "app"),
    text_renderer: Callable[[dict[str, Any]], str] | None = None,
) -> Callable[..., Any]:
    """Register the audited callable through the rich SDK when it is installed.

    The unit tier deliberately has no MCP/Pydantic dependency. Its minimal fake
    server still receives the audited callable through the fallback path.
    """
    try:
        from typing import Annotated

        from mcp.types import CallToolResult, TextContent, ToolAnnotations
        from pydantic import BaseModel, ConfigDict
    except ImportError:
        return mcp.tool()(wrapped)

    class ToolResultEnvelope(BaseModel):
        model_config = ConfigDict(extra="allow")

        ok: bool
        error_type: str | None = None
        error: str | None = None
        details: dict[str, Any] | None = None

    output_annotation = Annotated[CallToolResult, ToolResultEnvelope]

    @functools.wraps(wrapped)
    def adapter(*args: Any, **kwargs: Any) -> Any:
        payload = wrapped(*args, **kwargs)
        if not isinstance(payload, dict):
            payload = {
                "ok": False,
                "error_type": "internal",
                "error": "tool returned a non-object result",
                "details": {"tool": name},
            }
        text = (
            text_renderer(payload)
            if text_renderer is not None
            else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structuredContent=payload,
            isError=payload.get("ok") is False,
        )

    original = inspect.unwrap(wrapped)
    signature = inspect.signature(original)
    resolved_annotations = get_type_hints(original, include_extras=True)
    parameters = [
        parameter.replace(annotation=resolved_annotations.get(parameter.name, parameter.annotation))
        for parameter in signature.parameters.values()
    ]
    adapter.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters,
        return_annotation=output_annotation,
    )
    adapter.__annotations__ = resolved_annotations
    adapter.__annotations__["return"] = output_annotation
    annotations = ToolAnnotations(
        title=title,
        readOnlyHint=behavior.read_only,
        destructiveHint=behavior.destructive,
        idempotentHint=behavior.idempotent,
        openWorldHint=behavior.open_world,
    )
    kwargs: dict[str, Any] = {
        "name": name,
        "title": title,
        "description": description,
        "annotations": annotations,
        "structured_output": True,
    }
    if resource_uri is not None:
        kwargs["resource_uri"] = resource_uri
        kwargs["visibility"] = list(app_visibility)
    return mcp.tool(
        **kwargs,
    )(adapter)
