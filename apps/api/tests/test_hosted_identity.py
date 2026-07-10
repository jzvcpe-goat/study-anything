from __future__ import annotations

import json
import time
import unittest

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from _path import ROOT  # noqa: F401

from study_anything.core.api_security import load_api_security_config
from study_anything.core.hosted_identity import (
    HostedAuthenticationError,
    HostedIdentityConfigurationError,
    load_hosted_identity_config,
)


class HostedIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
            cls.private_key.public_key(),
            as_dict=True,
        )
        cls.public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})

    def environment(self) -> dict[str, str]:
        return {
            "APP_ENV": "production",
            "API_BIND_HOST": "0.0.0.0",
            "STUDY_ANYTHING_API_AUTH_MODE": "oidc_jwt",
            "STUDY_ANYTHING_OIDC_ISSUER": "https://identity.example.test",
            "STUDY_ANYTHING_OIDC_AUDIENCE": "study-anything-api",
            "STUDY_ANYTHING_OIDC_TENANT_CLAIM": "org_id",
            "STUDY_ANYTHING_OIDC_JWKS_JSON": json.dumps({"keys": [self.public_jwk]}),
        }

    def token(self, **overrides: object) -> str:
        now = int(time.time())
        claims: dict[str, object] = {
            "iss": "https://identity.example.test",
            "aud": "study-anything-api",
            "sub": "user-123",
            "org_id": "tenant-a",
            "name": "Hosted Learner",
            "iat": now,
            "exp": now + 600,
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key", "typ": "at+jwt"},
        )

    def test_valid_token_builds_stable_opaque_principal(self) -> None:
        config = load_hosted_identity_config(self.environment())

        principal = config.authenticate(f"Bearer {self.token()}")
        same_principal = config.authenticate(f"Bearer {self.token()}")
        other_tenant = config.authenticate(
            f"Bearer {self.token(org_id='tenant-b')}"
        )
        public = principal.public_dict()

        self.assertTrue(principal.principal_id.startswith("prn_"))
        self.assertTrue(principal.tenant_id.startswith("tnt_"))
        self.assertEqual(principal.display_name, "Hosted Learner")
        self.assertEqual(principal.principal_id, same_principal.principal_id)
        self.assertNotEqual(principal.principal_id, other_tenant.principal_id)
        self.assertNotEqual(principal.tenant_id, other_tenant.tenant_id)
        self.assertNotIn("user-123", json.dumps(public))
        self.assertNotIn("tenant-a", json.dumps(public))
        self.assertFalse(public["raw_token_claims_included"])

    def test_signature_issuer_audience_and_tenant_are_required(self) -> None:
        config = load_hosted_identity_config(self.environment())

        for token in (
            self.token(iss="https://other.example.test"),
            self.token(aud="other-api"),
            self.token(org_id=""),
            self.token(exp=int(time.time()) - 120),
        ):
            with self.subTest(token=token[-12:]):
                with self.assertRaises(HostedAuthenticationError):
                    config.authenticate(f"Bearer {token}")

    def test_issuer_identifier_is_exact_and_rejects_credentials(self) -> None:
        environment = self.environment()
        environment["STUDY_ANYTHING_OIDC_ISSUER"] = "https://identity.example.test/"
        config = load_hosted_identity_config(environment)

        principal = config.authenticate(
            f"Bearer {self.token(iss='https://identity.example.test/')}"
        )
        self.assertTrue(principal.principal_id.startswith("prn_"))
        with self.assertRaises(HostedAuthenticationError):
            config.authenticate(f"Bearer {self.token()}")

        environment["STUDY_ANYTHING_OIDC_ISSUER"] = (
            "https://embedded-user@identity.example.test"
        )
        with self.assertRaisesRegex(HostedIdentityConfigurationError, "without credentials"):
            load_hosted_identity_config(environment)

    def test_token_age_and_lifetime_are_bounded(self) -> None:
        config = load_hosted_identity_config(self.environment())
        now = int(time.time())

        with self.assertRaisesRegex(HostedAuthenticationError, "maximum age"):
            config.authenticate(
                f"Bearer {self.token(iat=now - 7200, exp=now + 60)}"
            )
        with self.assertRaisesRegex(HostedAuthenticationError, "lifetime"):
            config.authenticate(
                f"Bearer {self.token(iat=now, exp=now + 7200)}"
            )

    def test_jwks_rejects_symmetric_or_ambiguous_configuration(self) -> None:
        environment = self.environment()
        environment["STUDY_ANYTHING_OIDC_JWKS_JSON"] = json.dumps(
            {"keys": [{"kid": "shared", "kty": "oct", "alg": "HS256", "k": "abc"}]}
        )
        with self.assertRaisesRegex(HostedIdentityConfigurationError, "unsupported algorithm"):
            load_hosted_identity_config(environment)

        environment = self.environment()
        environment["STUDY_ANYTHING_OIDC_JWKS_FILE"] = "/tmp/keys.json"
        with self.assertRaisesRegex(HostedIdentityConfigurationError, "exactly one"):
            load_hosted_identity_config(environment)

        environment = self.environment()
        private_jwk = dict(self.public_jwk)
        private_jwk["d"] = "must-not-be-stored"
        environment["STUDY_ANYTHING_OIDC_JWKS_JSON"] = json.dumps(
            {"keys": [private_jwk]}
        )
        with self.assertRaisesRegex(HostedIdentityConfigurationError, "private key"):
            load_hosted_identity_config(environment)

    def test_api_security_reports_hosted_boundary_without_jwks_or_claims(self) -> None:
        config = load_api_security_config(self.environment())
        public = config.public_dict()

        self.assertEqual(config.auth_mode, "oidc_jwt")
        self.assertTrue(config.bearer_required)
        self.assertFalse(config.token_required)
        self.assertTrue(public["multi_tenant_authentication"])
        self.assertEqual(public["hosted_identity"]["signing_key_count"], 1)
        self.assertFalse(public["hosted_identity"]["automatic_jwks_network_fetch"])
        self.assertNotIn("identity.example.test", json.dumps(public))


if __name__ == "__main__":
    unittest.main()
