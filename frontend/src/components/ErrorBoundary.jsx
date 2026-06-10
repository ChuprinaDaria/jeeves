import { Component } from 'react';

/**
 * Глобальний error boundary: без нього будь-яка помилка рендера
 * перетворює весь додаток на білий екран.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error('Unhandled render error:', error, info?.componentStack);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
          <div className="max-w-md w-full text-center space-y-4">
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
              Something went wrong
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              An unexpected error occurred. Please reload the page.
            </p>
            <button
              onClick={this.handleReload}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
