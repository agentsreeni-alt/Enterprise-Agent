"""Unit tests for connectors/notetaker.py parsing logic. No network calls --
_http_get is monkeypatched at the module level.
"""

from __future__ import annotations

import json

from enterprise_agent.connectors import notetaker


def test_vtt_to_text_strips_cues_and_timestamps():
    vtt = (
        "WEBVTT\n\n"
        "1\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "Hello there.\n\n"
        "2\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "General Kenobi."
    )
    assert notetaker._vtt_to_text(vtt) == "Hello there. General Kenobi."


def test_webhook_connector_parses_json_text_field(monkeypatch):
    monkeypatch.setattr(
        notetaker, "_http_get", lambda url, headers: json.dumps({"text": "hi"}).encode()
    )
    connector = notetaker.WebhookTranscriptConnector(
        url_template="https://x/{meeting_id}", api_key=None
    )
    transcript = connector.get_transcript("m1")
    assert transcript.text == "hi"
    assert transcript.meeting_id == "m1"


def test_webhook_connector_falls_back_to_raw_text(monkeypatch):
    monkeypatch.setattr(notetaker, "_http_get", lambda url, headers: b"plain text body")
    connector = notetaker.WebhookTranscriptConnector(
        url_template="https://x/{meeting_id}", api_key=None
    )
    transcript = connector.get_transcript("m1")
    assert transcript.text == "plain text body"


def test_webhook_connector_sends_bearer_token_when_api_key_set(monkeypatch):
    seen_headers = {}

    def fake_http_get(url, headers):
        seen_headers.update(headers)
        return b"{}"

    monkeypatch.setattr(notetaker, "_http_get", fake_http_get)
    connector = notetaker.WebhookTranscriptConnector(
        url_template="https://x/{meeting_id}", api_key="secret"
    )
    connector.get_transcript("m1")
    assert seen_headers["Authorization"] == "Bearer secret"
