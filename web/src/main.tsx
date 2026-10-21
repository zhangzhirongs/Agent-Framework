import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import { TooltipProvider } from "./components/motion/tooltip";
import { App } from "./App";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <MotionConfig reducedMotion="user">
    <TooltipProvider delay={400}>
      <App />
    </TooltipProvider>
  </MotionConfig>,
);
