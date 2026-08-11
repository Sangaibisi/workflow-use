"""Tests for the idempotency-aware retry loop and redirect-tolerant URL matching.

The retry loop used to re-execute side-effectful actions (click/key_press)
whenever a verifier returned False. Since several verifiers are over-strict
(exact URL equality after redirects, strip-equality on masked inputs), the
engine would re-click submit buttons against pages where the action had
already taken effect - duplicate form posts/orders. These tests pin the
guard behavior.

Run with: ``uv run pytest tests/test_retry_idempotency.py``
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor

# --- URL equivalence ---------------------------------------------------------------


class TestUrlsEquivalent:
	def test_exact_match(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://a.com/x', 'https://a.com/x')

	def test_fragment_and_trailing_slash(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://a.com/x/#top', 'https://a.com/x')

	def test_scheme_upgrade(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://a.com/x', 'http://a.com/x')

	def test_www_difference(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://www.a.com/x', 'https://a.com/x')

	def test_added_query_params(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://a.com/x?utm=1&locale=en', 'https://a.com/x')

	def test_locale_redirect_from_root(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://a.com/en/home', 'https://a.com')

	def test_deepened_path(self):
		assert SemanticWorkflowExecutor._urls_equivalent('https://a.com/login/identifier', 'https://a.com/login')

	def test_cross_host_fails(self):
		assert not SemanticWorkflowExecutor._urls_equivalent('https://evil.com/x', 'https://a.com/x')

	def test_different_path_fails(self):
		assert not SemanticWorkflowExecutor._urls_equivalent('https://a.com/error', 'https://a.com/checkout')

	def test_prefix_needs_segment_boundary(self):
		# /login-help is NOT a redirect variant of /login
		assert not SemanticWorkflowExecutor._urls_equivalent('https://a.com/login-help', 'https://a.com/login')


# --- Retry idempotency -------------------------------------------------------------


def make_executor(signatures):
	"""Build a SemanticWorkflowExecutor with the browser-touching pieces stubbed.

	*signatures* is a list the page-signature stub pops from (repeating the last
	value once exhausted), letting tests simulate 'page changed' vs 'no effect'.
	"""
	executor = SemanticWorkflowExecutor(browser=Mock())
	executor._refresh_semantic_mapping = AsyncMock()
	executor._detect_form_validation_errors = AsyncMock(return_value={})

	remaining = list(signatures)

	async def fake_signature():
		if len(remaining) > 1:
			return remaining.pop(0)
		return remaining[0]

	executor._capture_page_signature = fake_signature
	# Keep tests fast and error-path side-effect free
	executor.max_retries = 2
	executor.error_reporter = Mock(report_error=Mock(return_value='report'))
	return executor


def click_step():
	return SimpleNamespace(type='click', description='click submit', target_text='Submit', value=None)


def input_step():
	return SimpleNamespace(type='input', description='fill email', target_text='Email', value='a@b.c')


async def test_late_verification_does_not_reexecute():
	"""Executor ran once, verifier fails then passes on re-check -> no second dispatch."""
	executor = make_executor(signatures=['sig-a', 'sig-b'])
	step_executor = AsyncMock(return_value='result')
	verifier = AsyncMock(side_effect=[False, True])

	result = await executor._execute_with_verification_and_retry(step_executor, click_step(), verifier)

	assert result == 'result'
	assert step_executor.await_count == 1, 'side-effectful step must not be re-executed after dispatch'
	assert verifier.await_count == 2


async def test_changed_page_never_refires_click():
	"""Verifier always fails but the page changed after dispatch -> exactly one dispatch, step fails."""
	executor = make_executor(signatures=['sig-a', 'sig-b'])
	step_executor = AsyncMock(return_value='result')
	verifier = AsyncMock(return_value=False)

	with pytest.raises(Exception):
		await executor._execute_with_verification_and_retry(step_executor, click_step(), verifier)

	assert step_executor.await_count == 1, 'duplicate submission guard failed'


async def test_no_effect_click_is_retried():
	"""Click dispatched but page signature unchanged -> re-execution is safe and allowed."""
	executor = make_executor(signatures=['same-sig'])
	step_executor = AsyncMock(return_value='result')
	verifier = AsyncMock(side_effect=[False, False, True])

	result = await executor._execute_with_verification_and_retry(step_executor, click_step(), verifier)

	assert result == 'result'
	assert step_executor.await_count >= 2, 'no-observable-effect click should be re-executed'


async def test_executor_exception_is_retried():
	"""A raising executor (element not found) never dispatched - retry is always safe."""
	executor = make_executor(signatures=['sig-a', 'sig-b'])
	step_executor = AsyncMock(side_effect=[Exception('element not found'), 'result'])
	verifier = AsyncMock(return_value=True)

	result = await executor._execute_with_verification_and_retry(step_executor, click_step(), verifier)

	assert result == 'result'
	assert step_executor.await_count == 2


async def test_idempotent_input_is_retried():
	"""Input steps re-fill the same value - re-execution stays allowed."""
	executor = make_executor(signatures=['sig-a', 'sig-b'])
	step_executor = AsyncMock(return_value='result')
	verifier = AsyncMock(side_effect=[False, False, True])

	result = await executor._execute_with_verification_and_retry(step_executor, input_step(), verifier)

	assert result == 'result'
	# attempt 0 executes; attempt 1 re-checks (False) then re-executes; verifier passes
	assert step_executor.await_count == 2
