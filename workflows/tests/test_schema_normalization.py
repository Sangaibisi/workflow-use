"""LLM/legacy step-vocabulary normalization at schema load.

Generated workflows routinely arrive with 'keypress' instead of 'key_press'
or with the two extraction vocabularies crossed; these used to reject the
entire file at load time.

Run with: ``uv run pytest tests/test_schema_normalization.py``
"""

import pytest
from pydantic import ValidationError

from workflow_use.schema.views import (
	ExtractStep,
	KeyPressStep,
	PageExtractionStep,
	WorkflowDefinitionSchema,
)


def _wf(steps):
	return WorkflowDefinitionSchema(
		name='t', description='t', version='1.0', steps=steps, input_schema=[]
	)


class TestStepVocabularyNormalization:
	def test_keypress_spelling_is_accepted(self):
		wf = _wf([{'type': 'keypress', 'key': 'Enter', 'description': 'press enter'}])
		assert isinstance(wf.steps[0], KeyPressStep)
		assert wf.steps[0].type == 'key_press'
		assert wf.steps[0].key == 'Enter'

	def test_canonical_key_press_still_works(self):
		wf = _wf([{'type': 'key_press', 'key': 'Tab'}])
		assert isinstance(wf.steps[0], KeyPressStep)

	def test_extract_with_goal_field_is_accepted(self):
		wf = _wf([{'type': 'extract', 'goal': 'grab the order id'}])
		assert isinstance(wf.steps[0], ExtractStep)
		assert wf.steps[0].extractionGoal == 'grab the order id'

	def test_extract_page_content_with_extraction_goal_is_accepted(self):
		wf = _wf([{'type': 'extract_page_content', 'extractionGoal': 'confirmation text'}])
		assert isinstance(wf.steps[0], PageExtractionStep)
		assert wf.steps[0].goal == 'confirmation text'

	def test_correct_vocabulary_untouched(self):
		wf = _wf(
			[
				{'type': 'extract_page_content', 'goal': 'g'},
				{'type': 'extract', 'extractionGoal': 'e'},
			]
		)
		assert wf.steps[0].goal == 'g'
		assert wf.steps[1].extractionGoal == 'e'

	def test_unknown_type_still_rejected(self):
		with pytest.raises(ValidationError):
			_wf([{'type': 'teleport', 'destination': 'mars'}])
