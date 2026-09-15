import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { loadOpenData } from "./lib/openDataLoader";

// The case is computed from the bundled open data, so load it first (behind the splash screen); never wait forever.
const ready = Promise.race([loadOpenData(), new Promise((resolve) => setTimeout(resolve, 12_000))]);

void ready.then(() =>
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  ),
);
