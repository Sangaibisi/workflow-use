"""Tests for replay verification helpers hardened during the medium/low sweep.

Run with: ``uv run pytest tests/test_replay_verifiers.py``
"""

from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor as E


class TestInputValuesMatch:
	def test_exact(self):
		assert E._input_values_match('hello', 'hello')

	def test_whitespace_tolerant(self):
		assert E._input_values_match('  hello  ', 'hello')

	def test_masked_recorded_value_accepts_nonempty_field(self):
		# The field can't echo '********' back; a non-empty value is success
		assert E._input_values_match('********', 'realsecret')

	def test_masked_recorded_value_rejects_empty_field(self):
		assert not E._input_values_match('********', '')

	def test_formatted_phone_mask(self):
		# input mask reformats '5551234567' -> '(555) 123-4567'
		assert E._input_values_match('5551234567', '(555) 123-4567')

	def test_nbsp_and_curly_quotes(self):
		assert E._input_values_match('O’Brien', 'O’Brien')
		assert E._input_values_match('a b', 'a\xa0b')

	def test_genuinely_different_rejected(self):
		assert not E._input_values_match('red shoes', 'blue hat')


class TestParsePositionHint:
	def test_words_and_digits(self):
		assert E._parse_position_hint('first') == 1
		assert E._parse_position_hint('third') == 3
		assert E._parse_position_hint('last') == -1
		assert E._parse_position_hint('2') == 2
		assert E._parse_position_hint('2nd') == 2

	def test_item_of_phrasing(self):
		assert E._parse_position_hint('item 2 of 3') == 2

	def test_unparseable(self):
		assert E._parse_position_hint('somewhere') is None
		assert E._parse_position_hint(None) is None
