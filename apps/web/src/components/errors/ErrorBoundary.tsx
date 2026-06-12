import { Component, type ErrorInfo, type ReactNode } from "react";
import { FullError } from "./FullError";

type Props = {
  children: ReactNode;
};

type State = {
  error: Error | null;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("render crash", error, info);
  }

  render() {
    if (this.state.error) {
      return <FullError error={this.state.error} onAction={() => window.location.reload()} />;
    }
    return this.props.children;
  }
}
