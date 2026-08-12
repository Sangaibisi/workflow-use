"""Input-target resolution hardening found by an end-to-end replay on a real site.

Replaying a Wikipedia recording failed with a bare ``KeyError: 'type'``: the
step's target_text had fallen back to the field's name ('search'), the direct
selector '#search' matched Wikipedia's <form id="search"> instead of the input
inside it, and the shape probe then returned a dict with no 'type' key at all
(CDP's returnByValue omits `undefined` values).

Run with: ``uv run pytest tests/test_input_target_resolution.py``
"""

import pytest

from workflow_use.workflow.semantic_executor import _ELEMENT_SHAPE_JS
from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor as E


class _FakeElement:
	def __init__(self, tag):
		self.tag = tag


class _Executor:
	"""Minimal stand-in exposing only what the helpers under test touch."""

	def __init__(self, tag_by_selector):
		self.tag_by_selector = tag_by_selector
		self.probed = []

	async def _get_elements_by_selector(self, selector):
		# Absent key = no such element; a None value = element present but the
		# shape probe can't report a tag.
		if selector not in self.tag_by_selector:
			return []
		return [_FakeElement(self.tag_by_selector[selector])]

	async def _element_evaluate(self, element, js):
		self.probed.append(js)
		if element.tag is None:
			return {}  # what CDP returns for an element with no .type/.value
		return {'tagName': element.tag, 'type': '', 'value': '', 'isContentEditable': False}

	_selector_tag_matches = E._selector_tag_matches


class TestSelectorTagMatches:
	async def test_rejects_wrapper_with_shared_id(self):
		"""'#search' is Wikipedia's <form>, not the <input> that was recorded."""
		ex = _Executor({'#search': 'FORM'})
		assert await ex._selector_tag_matches('#search', 'INPUT') is False

	async def test_accepts_matching_tag(self):
		ex = _Executor({"[name='search']": 'INPUT'})
		assert await ex._selector_tag_matches("[name='search']", 'INPUT') is True

	async def test_case_insensitive(self):
		ex = _Executor({'#bio': 'TEXTAREA'})
		assert await ex._selector_tag_matches('#bio', 'textarea') is True

	async def test_missing_element_is_not_a_match(self):
		ex = _Executor({})
		assert await ex._selector_tag_matches('#nope', 'INPUT') is False

	async def test_unknown_tag_does_not_block(self):
		"""If the probe can't report a tag, don't veto the candidate."""
		ex = _Executor({'#weird': None})
		assert await ex._selector_tag_matches('#weird', 'INPUT') is True

	async def test_uses_the_shared_shape_probe(self):
		ex = _Executor({'#x': 'INPUT'})
		await ex._selector_tag_matches('#x', 'INPUT')
		assert ex.probed == [_ELEMENT_SHAPE_JS]


class TestElementShapeProbe:
	"""The probe must always return every key, whatever the element is."""

	@pytest.mark.parametrize('field', ['tagName', 'type', 'value', 'isContentEditable'])
	def test_probe_defines_every_field(self, field):
		assert f'{field}:' in _ELEMENT_SHAPE_JS

	def test_probe_coerces_types(self):
		# String()/Boolean() coercion is what keeps `undefined` keys from being
		# dropped by CDP's returnByValue serialization.
		assert "String(this.tagName || '')" in _ELEMENT_SHAPE_JS
		assert "String(this.type || '')" in _ELEMENT_SHAPE_JS
		assert 'Boolean(this.isContentEditable)' in _ELEMENT_SHAPE_JS

	def test_probe_is_callfunctionon_form(self):
		# Runtime.callFunctionOn takes a function declaration, not an arrow body
		assert _ELEMENT_SHAPE_JS.strip().startswith('(function()')
