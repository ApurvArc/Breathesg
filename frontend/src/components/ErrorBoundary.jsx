import React from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';
import { primaryButtonClass } from './ui';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-surface-container-lowest p-6 text-center">
          <div className="mb-6 grid h-20 w-20 place-items-center rounded-full bg-error-container text-error">
            <AlertTriangle size={40} />
          </div>
          <h1 className="mb-2 font-display-lg text-3xl font-extrabold text-on-surface">Something went wrong</h1>
          <p className="mb-8 max-w-md text-on-surface-variant leading-relaxed">
            A rendering error occurred in the application. Don't worry, your data is safe.
          </p>
          <div className="flex gap-4">
            <button
              onClick={() => window.location.assign('/')}
              className={primaryButtonClass}
            >
              <RefreshCcw size={18} />
              Reload Application
            </button>
          </div>
          {process.env.NODE_ENV === 'development' && (
            <pre className="mt-10 max-w-4xl overflow-auto rounded-lg bg-surface-container-highest p-4 text-left font-label-mono text-xs text-on-surface-variant">
              {this.state.error?.stack}
            </pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
