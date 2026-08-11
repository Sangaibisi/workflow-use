import { Edge, Node } from '@xyflow/react';
import { Workflow, WorkflowMetadata } from '../types/workflow-layout.types';
import { NodeData, StepData } from '../types/node-config-menu.types';

export function jsonToFlow(workflow: string): {
  nodes: Node<NodeData>[];
  edges: Edge[];
  metadata: WorkflowMetadata;
} {
  let parsedWorkflow: Workflow;
  try {
    parsedWorkflow = JSON.parse(workflow) as Workflow;
  } catch (e) {
    throw new Error(
      `Workflow file is not valid JSON: ${e instanceof Error ? e.message : String(e)}`
    );
  }
  if (!parsedWorkflow || !Array.isArray(parsedWorkflow.steps)) {
    throw new Error("Workflow file has no 'steps' array");
  }
  const nodes: Node<NodeData>[] = parsedWorkflow.steps.map((step: StepData, idx: number) => ({
    id: String(idx),
    data: {
      label: `${step.description}`,
      stepData: step,
      workflowName: parsedWorkflow.name
    },
    position: { x: 0, y: idx * 100 },
    type: 'default'
  }));

  const edges: Edge[] = parsedWorkflow.steps.slice(1).map((_, idx) => ({
    id: `e${idx}-${idx + 1}`,
    source: String(idx),
    target: String(idx + 1),
    animated: true,
  }));

  const metadata: WorkflowMetadata = {
    name: parsedWorkflow.name,
    description: parsedWorkflow.description,
    version: parsedWorkflow.version,
    input_schema: parsedWorkflow.input_schema,
    workflow_analysis: parsedWorkflow.workflow_analysis
  };

  return { nodes, edges, metadata };
}