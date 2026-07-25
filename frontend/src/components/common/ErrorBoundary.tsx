import React from 'react';
import Button from './Button';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches render errors that would otherwise unmount the whole tree and leave
 * a blank page with no way back. Class component because React exposes no hook
 * equivalent of componentDidCatch.
 */
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Unhandled render error', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-page">
        <div className="max-w-lg w-full bg-panel border border-line rounded-2xl shadow-md p-8 text-center">
          <h1 className="text-2xl font-bold text-ink mb-3">Something went wrong</h1>
          <p className="text-ink-2 mb-6">
            The page hit an unexpected error. Reloading usually clears it.
          </p>
          {/* The message itself stays out of the DOM — it can carry internal
              paths, query shapes or response fragments. componentDidCatch has
              already logged it with the full component stack for debugging. */}
          <Button onClick={() => window.location.reload()}>Reload the app</Button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
