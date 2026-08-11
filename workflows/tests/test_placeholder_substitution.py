"""Tests for safe placeholder substitution in Workflow._resolve_placeholders.

The old implementation used str.format(**context): a stray brace (JSON in a
value, '{' in recorded page text) raised ValueError/IndexError, one missing key
aborted resolution of every other placeholder, and attribute/index traversal
({obj.__class__}, {a[0]}) was a format-string injection surface.

Run with: ``uv run pytest tests/test_placeholder_substitution.py``
"""

from workflow_use.schema.views import WorkflowDefinitionSchema
from workflow_use.workflow.service import Workflow


def make_workflow(context):
	wf = object.__new__(Workflow)  # no browser/controller needed for this method
	wf.context = context
	wf.schema = WorkflowDefinitionSchema(
		name='t', description='t', version='1', steps=[{'type': 'navigation', 'url': 'https://a.com'}], input_schema=[]
	)
	return wf


def test_basic_substitution():
	wf = make_workflow({'name': 'Ada'})
	assert wf._resolve_placeholders('hello {name}') == 'hello Ada'


def test_partial_resolution_with_missing_key():
	wf = make_workflow({'a': '1'})
	# str.format raised KeyError and returned the ORIGINAL string - {a} stayed unresolved
	assert wf._resolve_placeholders('{a} and {missing}') == '1 and {missing}'


def test_json_braces_do_not_crash():
	wf = make_workflow({'q': 'x'})
	text = 'payload {"key": "value"} with {q}'
	assert wf._resolve_placeholders(text) == 'payload {"key": "value"} with x'


def test_positional_placeholder_is_left_alone():
	wf = make_workflow({})
	# str.format raised IndexError here (uncaught -> crashed the run)
	assert wf._resolve_placeholders('array {0} stays') == 'array {0} stays'


def test_no_attribute_traversal():
	wf = make_workflow({'obj': object()})
	# str.format would resolve {obj.__class__} - an injection surface
	assert wf._resolve_placeholders('{obj.__class__}') == '{obj.__class__}'


def test_escaped_braces():
	wf = make_workflow({'v': 'x'})
	assert wf._resolve_placeholders('literal {{v}} and real {v}') == 'literal {v} and real x'


def test_non_string_values_stringified():
	wf = make_workflow({'n': 42})
	assert wf._resolve_placeholders('count: {n}') == 'count: 42'
