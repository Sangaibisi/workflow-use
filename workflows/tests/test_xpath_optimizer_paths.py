"""Regression tests for the XPath optimizer's generated-path validity.

The optimizer used to emit two classes of poisoned alternatives:
- root-anchored "shortened" paths ('/div[1]/input[2]') that can never match
  because the document root is <html>;
- a hardcoded '(//table//tag)[1]' that targets the FIRST occurrence no
  matter which one was recorded.

Run with: ``uv run pytest tests/test_xpath_optimizer_paths.py``
"""

import re

from workflow_use.healing.xpath_optimizer import XPathOptimizer, escape_xpath_string


def _optimize(xpath, element_info=None, max_alternatives=5):
	return XPathOptimizer().optimize_xpath(xpath, element_info, max_alternatives=max_alternatives)


class TestNoDeadPaths:
	def test_no_root_anchored_shortened_path(self):
		"""A shortened path must never be absolute-from-root ('/div/...')."""
		xpath = '/html/body/div[2]/div[1]/section/div[3]/span[2]/input[1]'
		for alt in _optimize(xpath, {'tag': 'input', 'text': '', 'attributes': {}}):
			if alt == xpath:
				continue  # the absolute fallback itself is fine
			assert not re.match(r'^/[a-zA-Z]', alt), f'root-anchored dead path emitted: {alt}'

	def test_shortened_path_anchors_at_stable_tag(self):
		xpath = '/html/body/div[2]/form/div[1]/input[2]'
		alts = _optimize(xpath, None)
		shortened = [a for a in alts if a.startswith('//form')]
		assert shortened, f'expected a //form-anchored shortening in {alts}'
		assert '//form/div[1]/input[2]' in alts

	def test_shortened_path_preserves_anchor_index_as_document_position(self):
		"""form[2] outside its parent context reads as (//form)[2]."""
		xpath = '/html/body/div[1]/form[2]/div[3]/fieldset/input[1]'
		alts = _optimize(xpath, None)
		assert any(a.startswith('(//form)[2]/') for a in alts), alts

	def test_no_hardcoded_first_occurrence_selector(self):
		"""The recorded element may be ANY row - '( ... )[1]' picked the first."""
		xpath = '/html/body/table/tbody/tr[3]/td[2]/a'
		element_info = {'tag': 'a', 'text': 'Details', 'attributes': {}}
		for alt in _optimize(xpath, element_info):
			assert not re.search(r'^\(//table//a\)\[1\]$', alt), f'wrong-element selector emitted: {alt}'

	def test_unparseable_segment_disables_optimization(self):
		"""Skipping an unparseable segment used to silently drop a DOM level."""
		xpath = '/html/body/div[2]/*[3]/form/input[1]'
		alts = _optimize(xpath, None, max_alternatives=4)
		assert alts == [xpath], f'only the absolute fallback is trustworthy here, got {alts}'

	def test_short_paths_are_left_alone(self):
		xpath = '/html/body/form/input'
		alts = _optimize(xpath, None, max_alternatives=3)
		assert alts[-1] == xpath


class TestEscapeXpathString:
	def test_plain(self):
		assert escape_xpath_string('hello') == "'hello'"

	def test_single_quote_uses_double(self):
		assert escape_xpath_string("it's") == '"it\'s"'

	def test_double_quote_uses_single(self):
		assert escape_xpath_string('say "hi"') == '\'say "hi"\''

	def test_both_quotes_use_concat(self):
		out = escape_xpath_string('a\'b"c')
		assert out.startswith('concat(')
		assert '"\'"' in out

	def test_empty(self):
		assert escape_xpath_string('') == "''"
