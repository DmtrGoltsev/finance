import json
import re
import time
from datetime import UTC
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from app.config import Settings
from app.investments.hmac_auth import sign_callback

INGRESS_PATH = "/webhook/internal/finance/investments/recommendations/v1"


class DeliveryError(Exception):
    """Only a fixed error code may cross the logging boundary."""


class InvalidToken(DeliveryError):
    pass


class N8nTransport:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        url = urlsplit(settings.delivery_n8n_url)
        if (
            url.scheme not in {"http", "https"}
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path != INGRESS_PATH
            or url.hostname not in {"n8n", "finance-n8n", "localhost", "127.0.0.1"}
        ):
            raise DeliveryError("INVALID_INTERNAL_URL")
        if not settings.delivery_ingress_secret or len(settings.delivery_ingress_secret) < 32:
            raise DeliveryError("INGRESS_SECRET_REQUIRED")
        if settings.delivery_ingress_secret.startswith("replace-"):
            raise DeliveryError("INGRESS_PLACEHOLDER_FORBIDDEN")

    def send(self, event):
        created = (
            event.created_at.replace(tzinfo=UTC)
            if not event.created_at.tzinfo
            else event.created_at
        )
        body = json.dumps(
            {
                "schemaVersion": 1,
                "eventId": str(event.id),
                "jobId": str(event.aggregate_id),
                "attempt": event.attempt_count + 1,
                "createdAt": created.isoformat(),
                "analysisPackage": event.payload_safe,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        timestamp, nonce = int(time.time()), uuid4().hex
        signature = sign_callback(
            secret=self.settings.delivery_ingress_secret,
            method="POST",
            canonical_path=INGRESS_PATH,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
        response = self.client.post(
            self.settings.delivery_n8n_url,
            content=body,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Finance-Timestamp": str(timestamp),
                "X-Finance-Nonce": nonce,
                "X-Finance-Signature": signature,
            },
        )
        if response.status_code != 202:
            raise DeliveryError("N8N_NOT_ACCEPTED")
        ack = response.json()
        if ack.get("accepted") is not True or ack.get("eventId") != str(event.id):
            raise DeliveryError("N8N_INVALID_ACK")


class FcmTransport:
    def __init__(self, settings: Settings, client=None, credentials=None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        self.credentials = credentials
        if (
            settings.fcm_enabled
            and credentials is None
            and not (settings.fcm_credentials_file or settings.fcm_credentials_json)
        ):
            raise DeliveryError("FCM_CREDENTIALS_REQUIRED")
        if settings.fcm_enabled and not re.fullmatch(
            r"[a-z][a-z0-9-]{4,62}", settings.fcm_project_id
        ):
            raise DeliveryError("FCM_PROJECT_REQUIRED")

    def _access_token(self):
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials

        if self.credentials is None:
            scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
            if self.settings.fcm_credentials_file:
                self.credentials = Credentials.from_service_account_file(
                    self.settings.fcm_credentials_file, scopes=scopes
                )
            elif self.settings.fcm_credentials_json:
                self.credentials = Credentials.from_service_account_info(
                    json.loads(self.settings.fcm_credentials_json), scopes=scopes
                )
            else:
                raise DeliveryError("FCM_CREDENTIALS_REQUIRED")
        if not self.credentials.valid:
            request = Request()
            self.credentials.refresh(lambda **kwargs: request(**{**kwargs, "timeout": 15}))
        return self.credentials.token

    def send(self, token, event, session_id):
        if not self.settings.fcm_enabled:
            raise DeliveryError("FCM_DISABLED")
        job_id = str(event.payload_safe["jobId"])
        response = self.client.post(
            f"https://fcm.googleapis.com/v1/projects/{self.settings.fcm_project_id}/messages:send",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            json={
                "message": {
                    "token": token,
                    "data": {
                        "type": "investment_recommendation",
                        "eventId": str(event.id),
                        "jobId": job_id,
                        "sessionId": str(session_id),
                        "body": "Анализ портфеля готов",
                        "deepLink": f"finance://investments/recommendations?jobId={job_id}",
                    },
                    "android": {"priority": "high", "ttl": "86400s"},
                }
            },
        )
        if response.status_code != 200:
            # INVALID_ARGUMENT alone can mean a bad payload, not an invalid device token.
            details = response.json().get("error", {}).get("details", [])
            if any(
                d.get("@type", "").endswith("google.firebase.fcm.v1.FcmError")
                and d.get("errorCode") == "UNREGISTERED"
                for d in details
            ):
                raise InvalidToken("FCM_UNREGISTERED")
            raise DeliveryError("FCM_NOT_ACCEPTED")
        if (
            not response.json()
            .get("name", "")
            .startswith(f"projects/{self.settings.fcm_project_id}/messages/")
        ):
            raise DeliveryError("FCM_INVALID_ACK")
