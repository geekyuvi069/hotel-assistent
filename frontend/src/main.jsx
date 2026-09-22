import { Component } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// Without this, any uncaught render error blanks the whole app to a white screen with no way to recover.
class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("App crashed:", error, info.componentStack);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, fontFamily: "sans-serif" }}>
          <h1>Something went wrong</h1>
          <p>Please reload the page. If this keeps happening, contact the front desk.</p>
          <button onClick={() => location.reload()}>Reload</button>
          <pre style={{ marginTop: 16, fontSize: 12, color: "#777", whiteSpace: "pre-wrap" }}>{String(this.state.error?.stack || this.state.error)}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
