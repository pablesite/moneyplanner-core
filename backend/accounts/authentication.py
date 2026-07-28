from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.exceptions import InvalidToken, TokenBackendError
from rest_framework_simplejwt.settings import api_settings

from .models import ExternalIdentity


class CoreJWTAuthentication(JWTAuthentication):
    _external_source = "external"
    _password_change_bootstrap_path = "/api/family-members/ensure-primary/"

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        token = self.get_validated_token(raw_token)
        source = (
            token.get("_identity_source")
            if isinstance(token, dict)
            else getattr(token, "_identity_source", "core")
        )
        if source == self._external_source:
            trusted_bootstrap = (
                request.path == self._password_change_bootstrap_path
                and token.get("core_bootstrap") is True
            )
            if trusted_bootstrap:
                return self.get_user(token), token
            session = self._introspect_external_session(raw_token.decode("utf-8"))
            if session.get("must_change_password") is True:
                raise AuthenticationFailed(
                    "Password change required.",
                    code="password_change_required",
                )
        return self.get_user(token), token

    @staticmethod
    def _introspect_external_session(raw_token: str) -> dict:
        url = getattr(settings, "SAAS_AUTH_INTROSPECTION_URL", "").strip()
        secret = getattr(settings, "CORE_LINKING_SHARED_SECRET", "").strip()
        if not url or not secret:
            raise AuthenticationFailed("External session validation is not configured.")
        request = Request(
            url,
            data=json.dumps({"token": raw_token}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-SaaS-Bridge-Secret": secret,
            },
            method="POST",
        )
        timeout = float(getattr(settings, "SAAS_AUTH_INTROSPECTION_TIMEOUT_SECONDS", 2))
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise AuthenticationFailed("External session validation failed.") from exc
        if not isinstance(payload, dict):
            raise AuthenticationFailed("External session validation returned invalid data.")
        return payload

    def _external_token_backend(self) -> TokenBackend:
        return TokenBackend(
            algorithm=api_settings.ALGORITHM,
            signing_key=getattr(settings, "EXTERNAL_JWT_SIGNING_KEY", settings.SECRET_KEY),
            verifying_key="",
            audience=getattr(settings, "EXTERNAL_JWT_AUDIENCE", "moneyplanner-external-api"),
            issuer=getattr(settings, "EXTERNAL_JWT_ISSUER", "moneyplanner-external"),
            leeway=api_settings.LEEWAY,
            json_encoder=api_settings.JSON_ENCODER,
        )

    def get_validated_token(self, raw_token):
        try:
            token = super().get_validated_token(raw_token)
            setattr(token, "_identity_source", "core")
            return token
        except InvalidToken as core_error:
            if not getattr(settings, "AUTH_ACCEPT_EXTERNAL_TOKENS", False):
                raise core_error

            try:
                payload = self._external_token_backend().decode(raw_token, verify=True)
            except TokenBackendError:
                raise core_error

            if payload.get("token_type") != "access":
                raise core_error

            payload["_identity_source"] = self._external_source
            return payload

    def get_user(self, validated_token):
        if isinstance(validated_token, dict):
            source = validated_token.get("_identity_source")
        else:
            source = getattr(validated_token, "_identity_source", "core")

        if source != self._external_source:
            return super().get_user(validated_token)
        return self._get_or_create_user_from_external_token(validated_token)

    @staticmethod
    def _build_unique_username(base: str) -> str:
        user_model = get_user_model()
        candidate = base
        suffix = 1
        while user_model.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base}_{suffix}"
        return candidate

    @transaction.atomic
    def _get_or_create_user_from_external_token(self, payload: dict):
        user_model = get_user_model()
        external_user_id = payload.get(api_settings.USER_ID_CLAIM)
        if external_user_id in (None, ""):
            raise InvalidToken("External token without user_id.")

        external_user_id_str = str(external_user_id)
        identity = (
            ExternalIdentity.objects.select_related("user")
            .filter(
                provider=ExternalIdentity.Provider.EXTERNAL,
                external_user_id=external_user_id_str,
            )
            .first()
        )
        if identity is not None:
            if not identity.user.is_active:
                raise AuthenticationFailed("User is inactive", code="user_inactive")
            return identity.user

        username = self._build_unique_username(f"external_user_{external_user_id_str}")
        user = user_model.objects.create_user(username=username, password=None, email="")
        ExternalIdentity.objects.create(
            user=user,
            provider=ExternalIdentity.Provider.EXTERNAL,
            external_user_id=external_user_id_str,
        )
        return user
