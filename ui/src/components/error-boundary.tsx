import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * App-level error boundary. A single malformed workflow file (unvalidated
 * JSON.parse in json-to-flow, an unexpected shape, etc.) used to throw during
 * render and white-screen the entire GUI. This catches it and shows a
 * recoverable message instead of a blank page.
 */
class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("GUI render error:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen flex-col items-center justify-center bg-[#2a2a2a] px-5 text-center text-white">
          <h2 className="mb-3 text-xl">Something went wrong</h2>
          <p className="mb-2 max-w-[520px] text-sm text-[#ccc]">
            The GUI hit an error while rendering — most often a malformed
            workflow file in <code>workflows/tmp</code>. The rest of the app is
            unaffected.
          </p>
          <pre className="mb-5 max-w-[520px] overflow-x-auto rounded bg-black/40 p-3 text-left text-xs text-[#ff9d9d]">
            {this.state.error.message}
          </pre>
          <button
            onClick={this.handleReset}
            className="rounded bg-blue-400 px-5 py-2 text-base font-bold text-white transition-colors hover:bg-blue-500"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
