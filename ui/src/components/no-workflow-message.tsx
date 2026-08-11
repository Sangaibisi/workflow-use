import React from 'react';
import RecordButton from './record-button';

interface NoWorkflowsMessageProps {
  onRecordingSaved: (workflowFile: string) => void;
}

const NoWorkflowsMessage: React.FC<NoWorkflowsMessageProps> = ({
  onRecordingSaved,
}) => {
  return (
    <div className="flex flex-col justify-center items-center h-screen bg-[#2a2a2a] text-white p-0 px-5 text-center">
      <img
        src="/browseruse.png"
        alt="Browser Use Logo"
        className="w-[150px] h-auto mb-[30px]"
      />
      <h2 className="text-xl mb-[10px]">No Workflows Found</h2>
      <p className="text-sm max-w-[500px] leading-normal mb-[10px]">
        Record your first workflow right here, or place an existing workflow
        file in the <code>workflows/tmp</code> folder.
      </p>
      {/* First-run users can record straight from the GUI - the empty state
          used to hide the record button entirely, forcing terminal use. */}
      <div className="mb-[30px]">
        <RecordButton onRecordingSaved={onRecordingSaved} />
      </div>
      <a
        href="https://github.com/browser-use/workflow-use"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block bg-blue-400 hover:bg-blue-500 text-white no-underline py-[10px] px-[20px] rounded font-bold text-base transition-colors"
      >
        Learn More
      </a>
    </div>
  );
};

export default NoWorkflowsMessage;
