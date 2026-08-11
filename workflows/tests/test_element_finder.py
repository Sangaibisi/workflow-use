"""Unit tests for ElementFinder - semantic matching against browser-use DOM state.

These tests build fake nodes shaped like the REAL EnhancedDOMTreeNode surface
(attributes dict, ax_node with name/role, get_all_children_text(), is_visible)
instead of idealized flat attributes like node.text - the original tests mocked
an API that doesn't exist, which is exactly how the finder shipped dead.

find_element_with_strategies returns (result, strategy_attempts); result is
(element_index, strategy_used) or None.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from workflow_use.workflow.element_finder import ElementFinder


class FakeNode:
	"""Mimics EnhancedDOMTreeNode's real read surface."""

	def __init__(self, tag_name='div', text='', attributes=None, ax_name='', ax_role='', is_visible=True):
		self.tag_name = tag_name
		self._text = text
		self.attributes = attributes or {}
		self.ax_node = SimpleNamespace(name=ax_name, role=ax_role)
		self.is_visible = is_visible

	def get_all_children_text(self, max_depth=-1):
		return self._text


def make_session(selector_map):
	session = Mock()
	session.get_current_page = AsyncMock(return_value=Mock())
	session.get_selector_map = AsyncMock(return_value=selector_map)
	return session


def strategy(type_, value, priority=1, metadata=None):
	return {'type': type_, 'value': value, 'priority': priority, 'metadata': metadata or {}}


class TestElementFinder:
	def setup_method(self):
		self.finder = ElementFinder()

	async def test_find_by_text_exact(self):
		session = make_session(
			{
				1: FakeNode(tag_name='button', text='Cancel'),
				2: FakeNode(tag_name='button', text='Submit'),
			}
		)
		result, attempts = await self.finder.find_element_with_strategies([strategy('text_exact', 'Submit')], session)
		assert result is not None
		index, used = result
		assert index == 2
		assert used['type'] == 'text_exact'
		assert attempts and attempts[-1].success

	async def test_find_by_role_text(self):
		session = make_session(
			{
				1: FakeNode(tag_name='a', text='Submit'),
				2: FakeNode(tag_name='button', text='Submit', attributes={'role': 'button'}),
			}
		)
		result, _ = await self.finder.find_element_with_strategies(
			[strategy('role_text', 'Submit', metadata={'role': 'button'})], session
		)
		assert result is not None
		assert result[0] == 2

	async def test_find_by_aria_label(self):
		session = make_session(
			{
				1: FakeNode(tag_name='button', attributes={'aria-label': 'Close dialog'}),
			}
		)
		result, _ = await self.finder.find_element_with_strategies([strategy('aria_label', 'Close dialog')], session)
		assert result is not None
		assert result[0] == 1

	async def test_aria_label_falls_back_to_ax_name(self):
		"""Accessible name computed by the browser counts when the attribute is absent."""
		session = make_session({1: FakeNode(tag_name='button', ax_name='Close dialog')})
		result, _ = await self.finder.find_element_with_strategies([strategy('aria_label', 'Close dialog')], session)
		assert result is not None

	async def test_find_by_placeholder(self):
		session = make_session({1: FakeNode(tag_name='input', attributes={'placeholder': 'Enter email'})})
		result, _ = await self.finder.find_element_with_strategies([strategy('placeholder', 'Enter email')], session)
		assert result is not None

	async def test_find_by_title(self):
		session = make_session({1: FakeNode(tag_name='span', attributes={'title': 'More info'})})
		result, _ = await self.finder.find_element_with_strategies([strategy('title', 'More info')], session)
		assert result is not None

	async def test_find_by_alt_text(self):
		session = make_session({1: FakeNode(tag_name='img', attributes={'alt': 'Company logo'})})
		result, _ = await self.finder.find_element_with_strategies([strategy('alt_text', 'Company logo')], session)
		assert result is not None

	async def test_find_by_fuzzy_text(self):
		session = make_session({1: FakeNode(tag_name='button', text='Submit Order')})
		result, _ = await self.finder.find_element_with_strategies(
			[strategy('text_fuzzy', 'Submit Ordr', metadata={'threshold': 0.8})], session
		)
		assert result is not None

	async def test_multiple_strategies_fallback(self):
		"""Second strategy matches when the first can't."""
		session = make_session({1: FakeNode(tag_name='input', attributes={'placeholder': 'Search here'})})
		result, attempts = await self.finder.find_element_with_strategies(
			[
				strategy('text_exact', 'Nonexistent', priority=1),
				strategy('placeholder', 'Search here', priority=2),
			],
			session,
		)
		assert result is not None
		assert result[1]['type'] == 'placeholder'
		assert len(attempts) == 2  # failed first + successful second

	async def test_no_match_returns_none_result(self):
		session = make_session({1: FakeNode(tag_name='button', text='Cancel')})
		result, attempts = await self.finder.find_element_with_strategies([strategy('text_exact', 'Missing')], session)
		assert result is None
		assert attempts and not attempts[0].success

	async def test_empty_strategies(self):
		result, attempts = await self.finder.find_element_with_strategies([], make_session({}))
		assert result is None
		assert attempts == []

	async def test_no_page_returns_none(self):
		session = Mock()
		session.get_current_page = AsyncMock(return_value=None)
		result, _ = await self.finder.find_element_with_strategies([strategy('text_exact', 'X')], session)
		assert result is None

	async def test_empty_selector_map(self):
		session = make_session({})
		result, _ = await self.finder.find_element_with_strategies([strategy('text_exact', 'X')], session)
		assert result is None

	async def test_invisible_node_rejected(self):
		session = make_session({1: FakeNode(tag_name='button', text='Submit', is_visible=False)})
		result, _ = await self.finder.find_element_with_strategies([strategy('text_exact', 'Submit')], session)
		assert result is None

	async def test_fuzzy_threshold_rejects_weak_match(self):
		session = make_session({1: FakeNode(tag_name='button', text='Completely different')})
		result, _ = await self.finder.find_element_with_strategies(
			[strategy('text_fuzzy', 'Submit Order', metadata={'threshold': 0.8})], session
		)
		assert result is None
