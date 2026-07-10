"""Offline OIDC JWT validation for hosted tenant principals."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping
import urllib.parse


HOSTED_IDENTITY_SCHEMA_VERSION = "study-anything-hosted-identity-v1"
SAFE_JWT_ALGORITHMS = ("ES256", "RS256")
SAFE_TOKEN_TYPES = {"JWT", "at+jwt"}
CLAIM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,63}$")


class HostedIdentityConfigurationError(ValueError):
    """Raised when hosted identity configuration is incomplete or unsafe."""


class HostedAuthenticationError(PermissionError):
    """Raised when a hosted bearer token cannot establish a tenant principal."""


@dataclass(frozen=True)
class HostedPrincipal:
    principal_id: str
    tenant_id: str
    display_name: str

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": HOSTED_IDENTITY_SCHEMA_VERSION,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "display_name": self.display_name,
            "authentication_mode": "oidc_jwt",
            "raw_subject_included": False,
            "raw_tenant_claim_included": False,
            "raw_token_claims_included": False,
        }


@dataclass(frozen=True)
class HostedIdentityConfig:
    issuer: str
    audience: str
    tenant_claim: str
    jwks_by_kid: Mapping[str, Mapping[str, Any]]
    jwks_source: str
    leeway_seconds: int = 30
    max_token_age_seconds: int = 3600
    algorithms: tuple[str, ...] = SAFE_JWT_ALGORITHMS

    def authenticate(self, authorization: str | None) -> HostedPrincipal:
        token = _bearer_token(authorization)
        try:
            import jwt
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise HostedIdentityConfigurationError(
                "Install the hosted extra to use STUDY_ANYTHING_API_AUTH_MODE=oidc_jwt."
            ) from exc

        try:
            header = jwt.get_unverified_header(token)
            algorithm = str(header.get("alg") or "")
            key_id = str(header.get("kid") or "")
            token_type = str(header.get("typ") or "")
            if header.get("crit"):
                raise HostedAuthenticationError(
                    "Hosted bearer token uses unsupported critical headers."
                )
            if algorithm not in self.algorithms:
                raise HostedAuthenticationError("Hosted bearer token algorithm is not allowed.")
            if token_type not in SAFE_TOKEN_TYPES:
                raise HostedAuthenticationError("Hosted bearer token type is not allowed.")
            jwk = self.jwks_by_kid.get(key_id)
            if not key_id or jwk is None:
                raise HostedAuthenticationError("Hosted bearer token signing key is unknown.")
            if jwk.get("alg") != algorithm:
                raise HostedAuthenticationError("Hosted bearer token key algorithm does not match.")
            signing_key = jwt.PyJWK.from_dict(dict(jwk), algorithm=algorithm)
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_seconds,
                options={
                    "require": ["iss", "aud", "sub", "exp", "iat", self.tenant_claim],
                    "verify_signature": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_sub": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                },
            )
        except HostedAuthenticationError:
            raise
        except Exception as exc:
            raise HostedAuthenticationError("Hosted bearer token is invalid.") from exc

        subject = _required_claim(claims, "sub")
        tenant = _required_claim(claims, self.tenant_claim)
        issued_at = _numeric_claim(claims, "iat")
        expires_at = _numeric_claim(claims, "exp")
        now = int(time.time())
        if now - issued_at > self.max_token_age_seconds + self.leeway_seconds:
            raise HostedAuthenticationError("Hosted bearer token exceeds the maximum age.")
        if expires_at - issued_at > self.max_token_age_seconds + self.leeway_seconds:
            raise HostedAuthenticationError("Hosted bearer token lifetime exceeds policy.")

        display_name = str(claims.get("name") or claims.get("preferred_username") or "Hosted user")
        return HostedPrincipal(
            principal_id=_opaque_id("prn", self.issuer, tenant, subject),
            tenant_id=_opaque_id("tnt", self.issuer, tenant),
            display_name=display_name.strip()[:80] or "Hosted user",
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": HOSTED_IDENTITY_SCHEMA_VERSION,
            "mode": "oidc_jwt",
            "issuer_configured": True,
            "audience_configured": True,
            "tenant_claim_required": True,
            "tenant_claim_name": self.tenant_claim,
            "allowed_algorithms": list(self.algorithms),
            "accepted_token_types": sorted(SAFE_TOKEN_TYPES),
            "jwks_source": self.jwks_source,
            "signing_key_count": len(self.jwks_by_kid),
            "automatic_jwks_network_fetch": False,
            "raw_jwks_included": False,
            "raw_claims_included": False,
            "secret_values_included": False,
        }


def load_hosted_identity_config(environ: Mapping[str, str]) -> HostedIdentityConfig:
    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HostedIdentityConfigurationError(
            "Install the hosted extra to use STUDY_ANYTHING_API_AUTH_MODE=oidc_jwt."
        ) from exc

    issuer = (environ.get("STUDY_ANYTHING_OIDC_ISSUER") or "").strip()
    audience = (environ.get("STUDY_ANYTHING_OIDC_AUDIENCE") or "").strip()
    tenant_claim = (environ.get("STUDY_ANYTHING_OIDC_TENANT_CLAIM") or "org_id").strip()
    jwks_json = (environ.get("STUDY_ANYTHING_OIDC_JWKS_JSON") or "").strip()
    jwks_file = (environ.get("STUDY_ANYTHING_OIDC_JWKS_FILE") or "").strip()
    leeway_seconds = _bounded_integer(
        environ.get("STUDY_ANYTHING_OIDC_LEEWAY_SECONDS") or "30",
        label="STUDY_ANYTHING_OIDC_LEEWAY_SECONDS",
        minimum=0,
        maximum=120,
    )
    max_token_age_seconds = _bounded_integer(
        environ.get("STUDY_ANYTHING_OIDC_MAX_TOKEN_AGE_SECONDS") or "3600",
        label="STUDY_ANYTHING_OIDC_MAX_TOKEN_AGE_SECONDS",
        minimum=300,
        maximum=86_400,
    )

    issuer_parts = urllib.parse.urlsplit(issuer)
    try:
        issuer_parts.port
    except ValueError as exc:
        raise HostedIdentityConfigurationError(
            "STUDY_ANYTHING_OIDC_ISSUER contains an invalid port."
        ) from exc
    if (
        issuer_parts.scheme != "https"
        or not issuer_parts.hostname
        or issuer_parts.username is not None
        or issuer_parts.password is not None
        or issuer_parts.query
        or issuer_parts.fragment
        or len(issuer) > 2048
    ):
        raise HostedIdentityConfigurationError(
            "STUDY_ANYTHING_OIDC_ISSUER must be an HTTPS issuer URL without credentials, query, or fragment."
        )
    if not audience or len(audience) > 256:
        raise HostedIdentityConfigurationError("STUDY_ANYTHING_OIDC_AUDIENCE is required.")
    if not CLAIM_NAME_PATTERN.fullmatch(tenant_claim):
        raise HostedIdentityConfigurationError(
            "STUDY_ANYTHING_OIDC_TENANT_CLAIM must be a safe claim name."
        )
    if bool(jwks_json) == bool(jwks_file):
        raise HostedIdentityConfigurationError(
            "Configure exactly one of STUDY_ANYTHING_OIDC_JWKS_JSON or "
            "STUDY_ANYTHING_OIDC_JWKS_FILE."
        )
    if jwks_file:
        try:
            jwks_text = Path(jwks_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise HostedIdentityConfigurationError("Cannot read the configured OIDC JWKS file.") from exc
        jwks_source = "file"
    else:
        jwks_text = jwks_json
        jwks_source = "environment"
    jwks_by_kid = _validate_jwks(jwks_text)
    for jwk in jwks_by_kid.values():
        try:
            jwt.PyJWK.from_dict(dict(jwk), algorithm=str(jwk["alg"]))
        except Exception as exc:
            raise HostedIdentityConfigurationError(
                "OIDC JWKS contains an invalid public signing key."
            ) from exc
    return HostedIdentityConfig(
        issuer=issuer,
        audience=audience,
        tenant_claim=tenant_claim,
        jwks_by_kid=jwks_by_kid,
        jwks_source=jwks_source,
        leeway_seconds=leeway_seconds,
        max_token_age_seconds=max_token_age_seconds,
    )


def _validate_jwks(value: str) -> dict[str, Mapping[str, Any]]:
    if len(value.encode("utf-8")) > 131_072:
        raise HostedIdentityConfigurationError("OIDC JWKS exceeds the 128 KiB limit.")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HostedIdentityConfigurationError("OIDC JWKS must be valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise HostedIdentityConfigurationError("OIDC JWKS requires a keys array.")
    if len(payload["keys"]) > 16:
        raise HostedIdentityConfigurationError("OIDC JWKS may contain at most 16 signing keys.")
    keys: dict[str, Mapping[str, Any]] = {}
    for item in payload["keys"]:
        if not isinstance(item, dict):
            raise HostedIdentityConfigurationError("OIDC JWKS entries must be objects.")
        key_id = str(item.get("kid") or "")
        algorithm = str(item.get("alg") or "")
        key_type = str(item.get("kty") or "")
        use = str(item.get("use") or "sig")
        if not key_id or len(key_id) > 128 or key_id in keys:
            raise HostedIdentityConfigurationError("OIDC JWKS key ids must be unique and non-empty.")
        if algorithm not in SAFE_JWT_ALGORITHMS:
            raise HostedIdentityConfigurationError("OIDC JWKS uses an unsupported algorithm.")
        if key_type not in {"EC", "RSA"} or use != "sig":
            raise HostedIdentityConfigurationError("OIDC JWKS must contain public signing keys.")
        expected_key_type = "RSA" if algorithm == "RS256" else "EC"
        if key_type != expected_key_type:
            raise HostedIdentityConfigurationError(
                "OIDC JWKS key type does not match its declared algorithm."
            )
        private_fields = {"d", "p", "q", "dp", "dq", "qi", "oth"}
        if private_fields.intersection(item):
            raise HostedIdentityConfigurationError(
                "OIDC JWKS must not contain private key material."
            )
        key_operations = item.get("key_ops")
        if key_operations is not None and (
            not isinstance(key_operations, list) or "verify" not in key_operations
        ):
            raise HostedIdentityConfigurationError(
                "OIDC JWKS key operations must allow signature verification."
            )
        keys[key_id] = item
    if not keys:
        raise HostedIdentityConfigurationError("OIDC JWKS must contain at least one signing key.")
    return keys


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HostedAuthenticationError("Hosted bearer token is required.")
    scheme, separator, credential = authorization.partition(" ")
    token = credential.strip()
    if not separator or scheme.lower() != "bearer" or not token:
        raise HostedAuthenticationError("Hosted bearer token is required.")
    return token


def _required_claim(claims: Mapping[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise HostedAuthenticationError("Hosted bearer token contains an invalid identity claim.")
    return value.strip()


def _numeric_claim(claims: Mapping[str, Any], name: str) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HostedAuthenticationError("Hosted bearer token contains an invalid time claim.")
    return int(value)


def _opaque_id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"


def _bounded_integer(value: str, *, label: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HostedIdentityConfigurationError(f"{label} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise HostedIdentityConfigurationError(f"{label} is outside the supported range.")
    return parsed
