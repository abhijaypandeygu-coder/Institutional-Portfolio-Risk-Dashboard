import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '24px',
          margin: '16px',
          backgroundColor: '#450a0a',
          border: '1px solid #dc2626',
          borderRadius: '8px',
          color: '#fecaca',
          fontFamily: 'monospace'
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: 'bold', color: '#f87171', marginBottom: '8px' }}>
            {this.props.fallbackTitle || 'Component Error'}
          </h2>
          <p style={{ fontSize: '14px', marginBottom: '12px' }}>
            <strong>Error:</strong> {this.state.error?.message}
          </p>
          <pre style={{
            fontSize: '12px',
            backgroundColor: '#1c1917',
            padding: '12px',
            borderRadius: '6px',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            color: '#fca5a5'
          }}>
            {this.state.error?.stack}
            {'\n\nComponent Stack:\n'}
            {this.state.errorInfo?.componentStack}
          </pre>
          <button
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            style={{
              marginTop: '16px',
              padding: '6px 14px',
              backgroundColor: '#b91c1c',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            Retry Component
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
