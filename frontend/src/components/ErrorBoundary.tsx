import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "./ui";

/** Keeps one failing view from blanking the whole application. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("View failed to render", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          error={new Error("This view could not be displayed. Your data is safe — retry, or reload the page.")}
          onRetry={() => this.setState({ error: null })}
        />
      );
    }
    return this.props.children;
  }
}
