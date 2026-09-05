import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import "@fontsource-variable/jost";
import "@fontsource/cormorant-garamond/500.css";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("The application root element is missing.");

createRoot(root).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
