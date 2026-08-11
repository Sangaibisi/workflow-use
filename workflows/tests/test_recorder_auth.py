"""Tests for the recorder event-server's request validation.

POST /event on 127.0.0.1:7331 used to accept requests from anyone: any web
page (via DNS rebinding or a crafted localhost request) or LAN process could
inject fake steps into an in-progress recording. The middleware requires the
per-session token handed to the recorder-launched extension, plus sane Host
and Origin headers.

Run with: ``uv run pytest tests/test_recorder_auth.py``
"""

from fastapi.testclient import TestClient

from workflow_use.recorder.service import RecordingService

BODY = {'type': 'RECORDING_STARTED', 'timestamp': 1, 'payload': {'message': 'x'}}


def make_client():
	service = RecordingService()
	return service, TestClient(service.app, base_url='http://127.0.0.1')


def test_rejects_without_token():
	_, client = make_client()
	assert client.post('/event', json=BODY).status_code == 403


def test_rejects_wrong_token():
	_, client = make_client()
	assert client.post('/event', json=BODY, headers={'X-Recorder-Token': 'nope'}).status_code == 403


def test_rejects_web_origin_even_with_token():
	service, client = make_client()
	response = client.post(
		'/event', json=BODY, headers={'X-Recorder-Token': service.session_token, 'Origin': 'https://evil.example'}
	)
	assert response.status_code == 403


def test_rejects_foreign_host_header():
	service, client = make_client()
	response = client.post('/event', json=BODY, headers={'X-Recorder-Token': service.session_token, 'Host': 'attacker.example'})
	assert response.status_code == 403


def test_accepts_extension_origin_with_token():
	service, client = make_client()
	response = client.post(
		'/event', json=BODY, headers={'X-Recorder-Token': service.session_token, 'Origin': 'chrome-extension://abc'}
	)
	assert response.status_code == 202


def test_accepts_tokenized_request_without_origin():
	"""Service-worker fetches may omit Origin entirely."""
	service, client = make_client()
	response = client.post('/event', json=BODY, headers={'X-Recorder-Token': service.session_token})
	assert response.status_code == 202


def test_tokens_are_per_session():
	first, _ = make_client()
	second, client = make_client()
	assert first.session_token != second.session_token
	response = client.post('/event', json=BODY, headers={'X-Recorder-Token': first.session_token})
	assert response.status_code == 403
