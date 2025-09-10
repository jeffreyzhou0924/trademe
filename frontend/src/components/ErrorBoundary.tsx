import React from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    console.error('🚨 ErrorBoundary捕获错误:', error);
    return {
      hasError: true,
      error
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('🚨 ErrorBoundary详细信息:', error, errorInfo);
    console.error('🚨 组件堆栈:', errorInfo.componentStack);
    
    this.setState({
      error,
      errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary p-4 bg-red-50 border border-red-200 rounded-lg">
          <h2 className="text-lg font-semibold text-red-800 mb-2">
            React渲染错误
          </h2>
          <div className="text-sm text-red-700 space-y-2">
            <p><strong>错误:</strong> {this.state.error?.message || 'Unknown error'}</p>
            <details className="mt-4">
              <summary className="cursor-pointer font-medium">错误详情</summary>
              <pre className="mt-2 text-xs bg-red-100 p-2 rounded overflow-auto">
                {this.state.error?.stack}
              </pre>
              {this.state.errorInfo && (
                <pre className="mt-2 text-xs bg-red-100 p-2 rounded overflow-auto">
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </details>
          </div>
          <button 
            onClick={() => this.setState({ hasError: false })}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            重试渲染
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;