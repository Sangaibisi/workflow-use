import json as _json
from inspect import Parameter, Signature
from pathlib import Path
from typing import Any

from browser_use.llm.base import BaseChatModel
from fastmcp import FastMCP

from workflow_use.schema.views import WorkflowDefinitionSchema
from workflow_use.workflow.service import Workflow


def get_mcp_server(
	llm_instance: BaseChatModel,
	page_extraction_llm: BaseChatModel | None = None,
	workflow_dir: str = './tmp',
	name: str = 'WorkflowService',
	description: str = 'Exposes workflows as MCP tools.',
):
	# fastmcp 3.x renamed the server-level `description` kwarg to `instructions`.
	mcp_app = FastMCP(name=name, instructions=description)

	_setup_workflow_tools(mcp_app, llm_instance, page_extraction_llm, workflow_dir)
	return mcp_app


def _setup_workflow_tools(
	mcp_app: FastMCP, llm_instance: BaseChatModel, page_extraction_llm: BaseChatModel | None, workflow_dir: str
):
	"""
	Scans a directory for workflow.json and workflow.yaml files, loads them, and registers them as tools
	with the FastMCP instance by dynamically setting function signatures.
	"""
	# Find both JSON and YAML workflow files
	json_files = list(Path(workflow_dir).glob('*.workflow.json'))
	yaml_files = list(Path(workflow_dir).glob('*.workflow.yaml'))
	yml_files = list(Path(workflow_dir).glob('*.workflow.yml'))
	workflow_files = json_files + yaml_files + yml_files

	print(f"[FastMCP Service] Found workflow files in '{workflow_dir}': {len(workflow_files)}")

	registered_tool_names: set[str] = set()

	for wf_file_path in workflow_files:
		try:
			print(f'[FastMCP Service] Loading workflow from: {wf_file_path}')
			schema = WorkflowDefinitionSchema.load_from_file(str(wf_file_path))

			# Build the input model WITHOUT a long-lived Workflow instance: sharing
			# one Workflow (hence one browser + one mutable context) across
			# concurrent invocations of the same tool interleaved their state. A
			# fresh Workflow is created per call inside the runner instead.
			input_model = Workflow(
				workflow_schema=schema, llm=llm_instance, page_extraction_llm=page_extraction_llm, browser=None, controller=None
			)._input_model

			params_for_signature = []
			annotations_for_runner = {}

			if hasattr(input_model, 'model_fields'):
				for field_name, model_field in input_model.model_fields.items():
					param_annotation = model_field.annotation if model_field.annotation is not None else Any

					param_default = Parameter.empty
					if not model_field.is_required():
						param_default = model_field.default if model_field.default is not None else None

					params_for_signature.append(
						Parameter(
							name=field_name,
							kind=Parameter.POSITIONAL_OR_KEYWORD,
							default=param_default,
							annotation=param_annotation,
						)
					)
					annotations_for_runner[field_name] = param_annotation

			dynamic_signature = Signature(params_for_signature)

			# Sanitize workflow name for the function name
			safe_workflow_name_for_func = ''.join(c if c.isalnum() else '_' for c in schema.name)
			dynamic_func_name = f'tool_runner_{safe_workflow_name_for_func}_{schema.version.replace(".", "_")}'

			# Define the actual function that will be called by FastMCP.
			# A fresh Workflow (own browser + context) is created per invocation so
			# concurrent calls of the same tool don't share mutable state.
			def create_runner(wf_schema: WorkflowDefinitionSchema):
				async def actual_workflow_runner(**kwargs):
					wf_instance = Workflow(
						workflow_schema=wf_schema,
						llm=llm_instance,
						page_extraction_llm=page_extraction_llm,
						browser=None,
						controller=None,
					)
					raw_result = await wf_instance.run(inputs=kwargs)
					# Return structured JSON, not a Python repr. model_dump handles
					# pydantic results; default=str covers stray non-serializables.
					try:
						payload = raw_result.model_dump() if hasattr(raw_result, 'model_dump') else raw_result
						return _json.dumps(payload, default=str)
					except Exception:
						return _json.dumps({'result': str(raw_result)})

				return actual_workflow_runner

			runner_func_impl = create_runner(schema)

			# Set the dunder attributes that FastMCP will inspect
			runner_func_impl.__name__ = dynamic_func_name
			runner_func_impl.__doc__ = schema.description
			runner_func_impl.__signature__ = dynamic_signature
			runner_func_impl.__annotations__ = annotations_for_runner

			# Tool name and description for FastMCP registration
			base_tool_name = f'{schema.name.replace(" ", "_")}_{schema.version}'
			# Two workflows with the same name+version would silently overwrite each
			# other's tool registration; suffix duplicates so both stay callable.
			unique_tool_name = base_tool_name
			dup_index = 2
			while unique_tool_name in registered_tool_names:
				unique_tool_name = f'{base_tool_name}_{dup_index}'
				dup_index += 1
			registered_tool_names.add(unique_tool_name)
			tool_description = schema.description

			tool_decorator = mcp_app.tool(name=unique_tool_name, description=tool_description)
			tool_decorator(runner_func_impl)

			param_names_for_log = list(dynamic_signature.parameters.keys())
			print(
				f"[FastMCP Service] Registered tool (via signature): '{unique_tool_name}' for '{schema.name}'. Params: {param_names_for_log}"
			)

		except Exception as e:
			print(f'[FastMCP Service] Failed to load or register workflow from {wf_file_path}: {e}')
			import traceback

			traceback.print_exc()
