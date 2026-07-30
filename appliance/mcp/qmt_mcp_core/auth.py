"""MCP bearer verification for static and external OAuth JWT deployments."""

from __future__ import annotations

import hmac
import json
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import CoreConfig

JwksFetcher = Callable[[], dict[str, Any]]


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("JWKS redirects are not allowed")


def _open_jwks(request: Request, timeout: float):
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


def _parse_scopes(claims: dict[str, Any]) -> list[str] | None:
    raw_scope = claims.get("scope")
    raw_scp = claims.get("scp")

    scope_values: list[str] | None = None
    if raw_scope is not None:
        if not isinstance(raw_scope, str):
            return None
        scope_values = raw_scope.split()

    scp_values: list[str] | None = None
    if raw_scp is not None:
        if not isinstance(raw_scp, list) or not all(isinstance(item, str) and item for item in raw_scp):
            return None
        scp_values = raw_scp

    if scope_values is not None and scp_values is not None and set(scope_values) != set(scp_values):
        return None
    values = scope_values if scope_values is not None else scp_values
    if values is None:
        return []
    if any(not value or any(ch.isspace() for ch in value) for value in values):
        return None
    return sorted(set(values))


class JwksCache:
    def __init__(
        self,
        url: str,
        *,
        ttl_s: int,
        timeout_s: float,
        max_bytes: int,
        fetcher: JwksFetcher | None = None,
    ):
        self.url = url
        self.ttl_s = ttl_s
        self.timeout_s = timeout_s
        self.max_bytes = max_bytes
        self.retry_s = min(30.0, max(1.0, float(ttl_s)))
        self.fetcher = fetcher or self._fetch_url
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._last_forced_refresh = 0.0
        self._lock = threading.Lock()

    def key(self, kid: str, *, algorithm: str) -> Any | None:
        with self._lock:
            now = time.monotonic()
            if now >= self._expires_at:
                try:
                    self._refresh(now)
                except Exception:
                    self._expires_at = now + self.retry_s
                    self._last_forced_refresh = now
                    raise
            key = self._keys.get(kid)
            if key is None and now - self._last_forced_refresh >= self.retry_s:
                self._last_forced_refresh = now
                try:
                    self._refresh(now)
                except Exception:
                    self._expires_at = now + self.retry_s
                    raise
                key = self._keys.get(kid)
            if key is None or key.algorithm_name != algorithm:
                return None
            return key.key

    def _refresh(self, now: float) -> None:
        import jwt

        document = self.fetcher()
        raw_keys = document.get("keys") if isinstance(document, dict) else None
        if not isinstance(raw_keys, list):
            raise ValueError("JWKS keys must be an array")
        parsed: dict[str, Any] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, dict) or raw_key.get("use", "sig") != "sig":
                continue
            kid = raw_key.get("kid")
            if not isinstance(kid, str) or not kid or kid in parsed:
                raise ValueError("JWKS signing keys require unique non-empty kid values")
            parsed[kid] = jwt.PyJWK.from_dict(raw_key)
        if not parsed:
            raise ValueError("JWKS did not contain a usable signing key")
        self._keys = parsed
        self._expires_at = now + self.ttl_s

    def _fetch_url(self) -> dict[str, Any]:
        request = Request(self.url, headers={"Accept": "application/json", "User-Agent": "qmt-mcp/021"})
        with _open_jwks(request, self.timeout_s) as response:
            final_url = getattr(response, "geturl", lambda: self.url)()
            parsed = urlparse(final_url)
            if parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("JWKS redirect resolved to an insecure URL")
            body = response.read(self.max_bytes + 1)
        if len(body) > self.max_bytes:
            raise ValueError("JWKS response exceeds configured limit")
        document = json.loads(body)
        if not isinstance(document, dict):
            raise ValueError("JWKS response must be an object")
        return document


class StaticTokenVerifier:
    def __init__(self, token: str, resource: str, scopes: tuple[str, ...]):
        self.token = token
        self.resource = resource
        self.scopes = sorted(set(scopes) | {"qmt:read", "qmt:admin"})

    async def verify_token(self, token: str):
        if not self.token or not hmac.compare_digest(token, self.token):
            return None
        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token,
            client_id="qmt-static",
            scopes=self.scopes,
            resource=self.resource or None,
            subject=None,
            claims={"iss": "qmt-static"},
        )


class JwtTokenVerifier:
    def __init__(self, config: CoreConfig, *, fetcher: JwksFetcher | None = None):
        self.issuer = config.oauth_issuer_url
        self.resource = config.oauth_resource_url
        self.algorithms = tuple(config.oauth_algorithms)
        self.clock_skew_s = config.oauth_clock_skew_s
        self.jwks = JwksCache(
            config.oauth_jwks_url,
            ttl_s=config.oauth_jwks_ttl_s,
            timeout_s=config.oauth_http_timeout_s,
            max_bytes=config.oauth_jwks_max_bytes,
            fetcher=fetcher,
        )

    async def verify_token(self, token: str):
        import anyio

        return await anyio.to_thread.run_sync(self._verify_sync, token)

    def _verify_sync(self, token: str):
        import jwt
        from mcp.server.auth.provider import AccessToken

        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or not kid or algorithm not in self.algorithms:
                return None
            key = self.jwks.key(kid, algorithm=algorithm)
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(self.algorithms),
                issuer=self.issuer,
                audience=self.resource,
                leeway=self.clock_skew_s,
                options={"require": ["iss", "aud", "exp"]},
            )
            scopes = _parse_scopes(claims)
            if scopes is None:
                return None
            client_id = claims.get("client_id") or claims.get("azp")
            if not isinstance(client_id, str) or not client_id:
                return None
            subject = claims.get("sub")
            if subject is not None and not isinstance(subject, str):
                return None
            expires_at = claims.get("exp")
            if not isinstance(expires_at, int):
                return None
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=expires_at,
                resource=self.resource,
                subject=subject,
                claims={"iss": self.issuer, "aud": claims.get("aud")},
            )
        except Exception:
            return None


class CompositeTokenVerifier:
    def __init__(self, *verifiers):
        self.verifiers = verifiers

    async def verify_token(self, token: str):
        for verifier in self.verifiers:
            result = await verifier.verify_token(token)
            if result is not None:
                return result
        return None


def build_token_verifier(config: CoreConfig):
    jwt_verifier = JwtTokenVerifier(config)
    if config.auth_mode == "oauth":
        return jwt_verifier
    if config.auth_mode == "hybrid":
        return CompositeTokenVerifier(
            StaticTokenVerifier(config.token, config.oauth_resource_url, config.oauth_scopes_supported),
            jwt_verifier,
        )
    return None
