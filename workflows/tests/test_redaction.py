"""Tests for sensitive-value redaction and sensitive-type default omission.

Run with: ``uv run pytest tests/test_redaction.py``
"""

from types import SimpleNamespace

from workflow_use.workflow.redaction import VALUE_MASK, redact_step_value
from workflow_use.workflow.variable_identifier import (
	SENSITIVE_VARIABLE_TYPES,
	VariableCandidate,
	VariableIdentifier,
	VariableType,
)


def step(**fields):
	return SimpleNamespace(**fields)


class TestRedactStepValue:
	def test_password_hint_masks(self):
		assert redact_step_value(step(target_text='Password'), 'hunter2') == VALUE_MASK

	def test_phone_type_hint_masks(self):
		assert redact_step_value(step(inputType='tel', target_text='Contact'), '5551234567') == VALUE_MASK

	def test_turkish_phone_label_masks(self):
		assert redact_step_value(step(target_text='Cep Telefon Numarası'), '5551234567') == VALUE_MASK

	def test_cc_autocomplete_selector_masks(self):
		assert redact_step_value(step(cssSelector='input[autocomplete="cc-number"]'), '4111111111111111') == VALUE_MASK

	def test_element_text_hint_masks(self):
		"""Legacy steps may only carry the hint in elementText."""
		assert redact_step_value(step(elementText='One-time verification code'), '123456') == VALUE_MASK

	def test_plain_field_untouched(self):
		assert redact_step_value(step(target_text='Search term'), 'red shoes') == 'red shoes'

	def test_hotel_is_not_tel(self):
		assert redact_step_value(step(target_text='Hotel name'), 'Grand Hotel') == 'Grand Hotel'

	def test_masked_stays_masked(self):
		assert redact_step_value(step(), VALUE_MASK) == VALUE_MASK


class TestSensitiveDefaults:
	def _schema_entry(self, variable_type, value, confidence, suggested_default):
		identifier = VariableIdentifier()
		candidate = VariableCandidate(
			value=value,
			variable_name='v',
			variable_type=variable_type,
			confidence=confidence,
			context={},
			suggested_default=suggested_default,
		)
		return identifier._generate_input_schema({'v': candidate})[0]

	def test_context_detected_password_gets_no_default(self):
		"""A 0.85-confidence password (context-detected) is still a secret."""
		entry = self._schema_entry(VariableType.PASSWORD, 's3cret!', 0.85, 's3cret!')
		assert 'default' not in entry

	def test_phone_gets_no_default(self):
		entry = self._schema_entry(VariableType.PHONE, '5551234567', 0.9, '5551234567')
		assert 'default' not in entry

	def test_masked_password_default_allowed(self):
		entry = self._schema_entry(VariableType.PASSWORD, '********', 0.85, '********')
		assert entry.get('default') == '********'

	def test_plain_string_keeps_default(self):
		entry = self._schema_entry(VariableType.STRING, 'red shoes', 0.7, 'red shoes')
		assert entry.get('default') == 'red shoes'

	def test_sensitive_set_covers_expected_types(self):
		assert {VariableType.PASSWORD, VariableType.CREDIT_CARD, VariableType.SSN} <= SENSITIVE_VARIABLE_TYPES
