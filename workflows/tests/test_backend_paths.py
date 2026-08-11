"""Tests for backend path safety and format-preserving writes.

Run with: ``uv run pytest tests/test_backend_paths.py``
"""

import json

import pytest
import yaml

from backend.service import WorkflowService


@pytest.fixture()
def service(tmp_path, monkeypatch):
	svc = WorkflowService.__new__(WorkflowService)
	svc.tmp_dir = tmp_path
	svc.log_dir = tmp_path / 'logs'
	svc.log_dir.mkdir()
	return svc


class TestResolveWorkflowPath:
	def test_normal_name_resolves_inside_tmp(self, service):
		p = service._resolve_workflow_path('a.workflow.yaml')
		assert p.parent == service.tmp_dir.resolve()

	def test_rejects_parent_traversal(self, service):
		with pytest.raises(ValueError):
			service._resolve_workflow_path('../../etc/passwd.workflow.yaml')

	def test_rejects_absolute_path(self, service):
		with pytest.raises(ValueError):
			service._resolve_workflow_path('/etc/evil.workflow.yaml')

	def test_rejects_nested_subdir(self, service):
		with pytest.raises(ValueError):
			service._resolve_workflow_path('sub/dir/a.workflow.yaml')

	def test_rejects_non_workflow_extension(self, service):
		with pytest.raises(ValueError):
			service._resolve_workflow_path('a.txt')


class TestDumpWorkflowPreservesFormat:
	def test_json_stays_json(self, service):
		f = service.tmp_dir / 'a.workflow.json'
		WorkflowService._dump_workflow({'name': 'x', 'steps': []}, f)
		# valid JSON, not YAML
		assert json.loads(f.read_text())['name'] == 'x'

	def test_yaml_stays_yaml(self, service):
		f = service.tmp_dir / 'a.workflow.yaml'
		WorkflowService._dump_workflow({'name': 'Türkçe', 'steps': []}, f)
		loaded = yaml.safe_load(f.read_text())
		assert loaded['name'] == 'Türkçe'


class TestGetWorkflowErrors:
	def test_missing_raises_filenotfound(self, service):
		with pytest.raises(FileNotFoundError):
			service.get_workflow('nope.workflow.yaml')

	def test_invalid_name_raises_valueerror(self, service):
		with pytest.raises(ValueError):
			service.get_workflow('../escape.workflow.yaml')
