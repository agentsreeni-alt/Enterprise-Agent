"""Real transcript-source integration for the Intake stage.

Deliberately NOT a single-vendor Otter.ai client: Otter has no
well-documented public API for third-party transcript retrieval, and
companies use all kinds of note-takers (Otter, Zoom Cloud Recording, Fireflies,
tl;dv, an internal relay, ...). Instead this module implements two concrete,
confidently-implementable backends behind the same `OtterConnector` Protocol
(`get_transcript(meeting_id) -> Transcript`), selected by
`ENTERPRISE_AGENT_TRANSCRIPT_SOURCE`:

- "zoom": Zoom's real Cloud Recording REST API (Server-to-Server OAuth).
  Well-documented, publicly available, no MCP server needed.
- "webhook": a generic HTTP+API-key escape hatch -- point it at whatever
  relay/webhook your actual note-taker (Otter, Fireflies, tl;dv, ...)
  exposes, or one you stand up yourself.

Uses stdlib `urllib` only, matching this package's policy of not adding new
third-party HTTP dependencies for a single connector.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from enterprise_agent.connectors.base import Transcript
from enterprise_agent.errors import RealModeError

TRANSCRIPT_SOURCE_ENV = "ENTERPRISE_AGENT_TRANSCRIPT_SOURCE"

ZOOM_ACCOUNT_ID_ENV = "ENTERPRISE_AGENT_ZOOM_ACCOUNT_ID"
ZOOM_CLIENT_ID_ENV = "ENTERPRISE_AGENT_ZOOM_CLIENT_ID"
ZOOM_CLIENT_SECRET_ENV = "ENTERPRISE_AGENT_ZOOM_CLIENT_SECRET"

WEBHOOK_URL_ENV = "ENTERPRISE_AGENT_TRANSCRIPT_WEBHOOK_URL"
WEBHOOK_API_KEY_ENV = "ENTERPRISE_AGENT_TRANSCRIPT_WEBHOOK_API_KEY"

ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE = "https://api.zoom.us/v2"


class NotetakerConfigError(RealModeError):
    """Raised synchronously, before any network call, when required config
    is missing or names an unknown source.
    """


class NotetakerRequestError(RealModeError):
    """Raised when the configured transcript source is reachable but
    doesn't return a usable transcript (HTTP error, missing transcript
    file, malformed response).
    """


def build_real_notetaker_connector(env: dict[str, str] | None = None):
    env = env if env is not None else os.environ
    source = env.get(TRANSCRIPT_SOURCE_ENV)
    if source == "zoom":
        account_id = env.get(ZOOM_ACCOUNT_ID_ENV)
        client_id = env.get(ZOOM_CLIENT_ID_ENV)
        client_secret = env.get(ZOOM_CLIENT_SECRET_ENV)
        if not (account_id and client_id and client_secret):
            raise NotetakerConfigError(
                f"{TRANSCRIPT_SOURCE_ENV}=zoom requires {ZOOM_ACCOUNT_ID_ENV}, "
                f"{ZOOM_CLIENT_ID_ENV}, and {ZOOM_CLIENT_SECRET_ENV} (a Server-to-"
                "Server OAuth app's credentials, from Zoom App Marketplace)."
            )
        return ZoomTranscriptConnector(
            account_id=account_id, client_id=client_id, client_secret=client_secret
        )
    if source == "webhook":
        url_template = env.get(WEBHOOK_URL_ENV)
        if not url_template:
            raise NotetakerConfigError(
                f"{TRANSCRIPT_SOURCE_ENV}=webhook requires {WEBHOOK_URL_ENV} (a URL "
                "template containing '{meeting_id}', e.g. "
                "'https://relay.example.com/transcripts/{meeting_id}')."
            )
        return WebhookTranscriptConnector(
            url_template=url_template, api_key=env.get(WEBHOOK_API_KEY_ENV)
        )
    raise NotetakerConfigError(
        f"{TRANSCRIPT_SOURCE_ENV} must be set to 'zoom' or 'webhook' for real "
        f"transcript integration (got {source!r})."
    )


def _http_get(url: str, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        raise NotetakerRequestError(f"GET {url} failed: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise NotetakerRequestError(f"GET {url} failed: {e.reason}") from e


def _vtt_to_text(vtt: str) -> str:
    """Strip WEBVTT cue numbers/timestamps down to plain spoken text."""
    lines = []
    for line in vtt.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "WEBVTT":
            continue
        if re.match(r"^\d+$", stripped):
            continue
        if "-->" in stripped:
            continue
        lines.append(stripped)
    return " ".join(lines)


@dataclass
class ZoomTranscriptConnector:
    account_id: str
    client_id: str
    client_secret: str

    def _access_token(self) -> str:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        url = f"{ZOOM_OAUTH_URL}?grant_type=account_credentials&account_id={self.account_id}"
        request = urllib.request.Request(
            url, headers={"Authorization": f"Basic {basic}"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as e:
            raise NotetakerRequestError(f"Zoom OAuth token request failed: HTTP {e.code}") from e
        token = data.get("access_token")
        if not token:
            raise NotetakerRequestError("Zoom OAuth response had no access_token")
        return token

    def get_transcript(self, meeting_id: str) -> Transcript:
        token = self._access_token()
        headers = {"Authorization": f"Bearer {token}"}
        recordings = json.loads(
            _http_get(f"{ZOOM_API_BASE}/meetings/{meeting_id}/recordings", headers)
        )
        transcript_file = next(
            (
                f
                for f in recordings.get("recording_files", [])
                if f.get("recording_type") == "audio_transcript"
                or f.get("file_type") == "TRANSCRIPT"
            ),
            None,
        )
        if transcript_file is None:
            raise NotetakerRequestError(
                f"Zoom meeting {meeting_id} has no transcript recording file"
            )
        vtt_bytes = _http_get(transcript_file["download_url"], headers)
        text = _vtt_to_text(vtt_bytes.decode("utf-8"))
        return Transcript(meeting_id=meeting_id, text=text, source="zoom")


@dataclass
class WebhookTranscriptConnector:
    url_template: str
    api_key: str | None

    def get_transcript(self, meeting_id: str) -> Transcript:
        url = self.url_template.format(meeting_id=meeting_id)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        raw = _http_get(url, headers)
        try:
            data = json.loads(raw)
            text = data["text"] if isinstance(data, dict) else raw.decode("utf-8")
        except (json.JSONDecodeError, KeyError):
            text = raw.decode("utf-8")
        return Transcript(meeting_id=meeting_id, text=text, source="webhook")
