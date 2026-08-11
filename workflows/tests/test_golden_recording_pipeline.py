"""Golden test for the record -> convert -> save -> load pipeline (no browser).

A representative recording (form with select/radio/checkbox, masked login
value, multi-site navigation, selector strategies) flows through the semantic
converter and save-time stripping, then must round-trip through the replay
schema and map onto registered controller actions. This pins the wire contract
that previously broke silently (dropped selects, stripped fallback fields,
plaintext defaults, steps whose types no controller action accepts).

Run with: ``uv run pytest tests/test_golden_recording_pipeline.py``
"""

import json

import pytest

from workflow_use.recorder.semantic_converter import (
	convert_recorded_workflow_to_semantic,
	strip_presentation_fields,
)
from workflow_use.schema.views import WorkflowDefinitionSchema

GOLDEN_RECORDING = {
	'workflow_analysis': 'recorded',
	'name': 'Golden Fixture',
	'description': 'recorded fixture',
	'version': '1.0',
	'input_schema': [],
	'steps': [
		{
			'type': 'navigation',
			'url': 'https://site-a.example/login',
			'timestamp': 1,
			'tabId': 7,
			'screenshot': 'data:image/jpeg;base64,AAAA',
		},
		{
			'type': 'input',
			'url': 'https://site-a.example/login',
			'frameUrl': 'https://site-a.example/login',
			'xpath': 'id("email")',
			'cssSelector': 'input#email[name="email"]',
			'elementTag': 'INPUT',
			'value': 'user@example.com',
			'targetText': 'Email',
			'target_text': 'Email',
			'selectorStrategies': [
				{'type': 'text_exact', 'value': 'Email', 'priority': 1, 'metadata': {'tag': 'input'}},
				{'type': 'placeholder', 'value': 'Email', 'priority': 4, 'metadata': {'tag': 'input'}},
			],
			'timestamp': 2,
			'tabId': 7,
			'screenshot': 'data:image/jpeg;base64,BBBB',
		},
		{
			'type': 'input',
			'url': 'https://site-a.example/login',
			'frameUrl': 'https://site-a.example/login',
			'xpath': 'id("password")',
			'cssSelector': 'input#password',
			'elementTag': 'INPUT',
			'value': '********',  # masked at capture; must stay masked
			'targetText': 'Password',
			'target_text': 'Password',
			'timestamp': 3,
			'tabId': 7,
		},
		{
			'type': 'select_change',
			'url': 'https://site-a.example/profile',
			'frameUrl': 'https://site-a.example/profile',
			'xpath': 'id("country")',
			'cssSelector': 'select#country',
			'elementTag': 'SELECT',
			'selectedValue': 'tr',
			'selectedText': 'Türkiye',
			'timestamp': 4,
			'tabId': 7,
		},
		{
			'type': 'click',
			'url': 'https://site-a.example/profile',
			'frameUrl': 'https://site-a.example/profile',
			'xpath': 'id("subscribe")',
			'cssSelector': 'input#subscribe[type="checkbox"]',
			'elementTag': 'INPUT',
			'elementText': '',
			'targetText': 'Subscribe to newsletter',
			'target_text': 'Subscribe to newsletter',
			'timestamp': 5,
			'tabId': 7,
		},
		{
			'type': 'key_press',
			'url': 'https://site-a.example/profile',
			'frameUrl': 'https://site-a.example/profile',
			'xpath': 'id("save")',
			'cssSelector': 'button#save',
			'elementTag': 'BUTTON',
			'key': 'Enter',
			'timestamp': 6,
			'tabId': 7,
		},
		{
			'type': 'navigation',
			'url': 'https://site-b.example/dashboard',  # deliberate cross-site jump
			'timestamp': 7,
			'tabId': 7,
		},
		{
			'type': 'scroll',
			'url': 'https://site-b.example/dashboard',
			'scrollX': 0,
			'scrollY': 640,
			'timestamp': 8,
			'tabId': 7,
		},
	],
}


@pytest.fixture()
def saved_workflow():
	converted = convert_recorded_workflow_to_semantic(json.loads(json.dumps(GOLDEN_RECORDING)))
	stripped = strip_presentation_fields(converted)
	# save/load round-trip exactly as the backend writes it
	return json.loads(json.dumps(stripped))


def test_every_step_survives_conversion(saved_workflow):
	types = [step['type'] for step in saved_workflow['steps']]
	assert types == [
		'navigation',
		'input',
		'input',
		'select_change',
		'click',
		'key_press',
		'navigation',
		'scroll',
	], f'steps dropped or reordered: {types}'


def test_schema_roundtrip(saved_workflow):
	schema = WorkflowDefinitionSchema(**saved_workflow)
	assert len(schema.steps) == 8


def test_presentation_fields_stripped_fallbacks_kept(saved_workflow):
	for step in saved_workflow['steps']:
		assert 'screenshot' not in step
		assert 'tabId' not in step
		assert 'timestamp' not in step
	email_step = saved_workflow['steps'][1]
	# Replay fallbacks must survive the wire and the save
	assert email_step['xpath'] == 'id("email")'
	assert email_step['elementTag'] == 'INPUT'
	assert email_step['selectorStrategies'][0]['type'] == 'text_exact'


def test_sensitive_values_never_persist_in_plaintext(saved_workflow):
	"""Variable identification parameterizes login fields; no secret may land on disk."""
	password_step = saved_workflow['steps'][2]
	# The masked capture is parameterized into a variable placeholder
	assert password_step['value'] == '{password}'

	schema_by_name = {entry['name']: entry for entry in saved_workflow['input_schema']}
	# High-confidence sensitive matches must NOT persist their raw value as default
	assert 'default' not in schema_by_name['email'], 'raw email persisted as plaintext default'
	# If the password entry carries a default at all, it is the mask - never a secret
	assert schema_by_name['password'].get('default', '********') == '********'

	serialized = json.dumps(saved_workflow)
	assert 'user@example.com' not in serialized.replace('"description": "Email (email)"', '')


def test_select_step_keeps_visible_text(saved_workflow):
	select_step = saved_workflow['steps'][3]
	assert select_step['selectedText'] == 'Türkiye'
	assert select_step['type'] == 'select_change'


def test_cross_site_navigation_preserved(saved_workflow):
	nav_urls = [step['url'] for step in saved_workflow['steps'] if step['type'] == 'navigation']
	assert 'https://site-b.example/dashboard' in nav_urls


def test_deterministic_steps_map_to_registered_actions(saved_workflow):
	"""Every deterministic step type must resolve to a registered controller action."""
	from workflow_use.controller.service import WorkflowController

	controller = WorkflowController()
	registered = set(controller.registry.registry.actions.keys())
	for step in saved_workflow['steps']:
		step_type = step['type']
		assert step_type in registered, f"step type '{step_type}' has no controller action (have: {sorted(registered)})"
		action_model = controller.registry.create_action_model(include_actions=[step_type])
		assert action_model.model_fields, f"empty action model for '{step_type}' - would no-op silently"


def test_container_and_sibling_hints_reach_saved_steps():
	"""containerContext/siblingContext from the extension become
	container_hint/position_hint - a pipeline that was dead because the
	converter read keys nothing emitted."""
	recording = {
		'name': 'Hints',
		'description': 'hint fixture',
		'version': '1.0',
		'input_schema': [],
		'steps': [
			{
				'type': 'click',
				'url': 'https://site.example',
				'cssSelector': 'button.save',
				'elementTag': 'BUTTON',
				'elementText': 'Save',
				'semanticInfo': {
					'labelText': 'Save',
					'containerContext': {'type': 'section', 'text': 'Billing address', 'id': ''},
					'siblingContext': {'position': 1, 'total': 3},
				},
			},
		],
	}
	converted = convert_recorded_workflow_to_semantic(recording)
	step = converted['steps'][0]
	assert step['container_hint'] == 'Billing address'
	assert step['position_hint'] == 'item 2 of 3'


def test_snake_case_hint_keys_also_accepted():
	recording = {
		'name': 'Hints',
		'description': 'hint fixture',
		'version': '1.0',
		'input_schema': [],
		'steps': [
			{
				'type': 'click',
				'cssSelector': 'button.save',
				'elementText': 'Save',
				'semanticInfo': {
					'labelText': 'Save',
					'container_context': {'type': 'fieldset', 'text': '', 'id': 'shipping-address'},
					'sibling_context': {'position': 0, 'total': 2},
				},
			},
		],
	}
	converted = convert_recorded_workflow_to_semantic(recording)
	step = converted['steps'][0]
	assert step['container_hint'] == 'Shipping Address'
	assert step['position_hint'] == 'item 1 of 2'


def test_tooling_metadata_survives_schema_roundtrip():
	"""variable_identifier writes workflow['metadata']; the schema used to drop
	it on the very next load/save."""
	raw = {
		'name': 'Meta',
		'description': 'metadata fixture',
		'version': '1.0',
		'input_schema': [],
		'steps': [{'type': 'navigation', 'url': 'https://site.example'}],
		'metadata': {'variables_auto_identified': True, 'identified_variable_count': 2},
	}
	schema = WorkflowDefinitionSchema(**raw)
	dumped = schema.model_dump()
	assert dumped['metadata'] == raw['metadata']
