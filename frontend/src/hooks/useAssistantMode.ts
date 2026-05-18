import { useCallback, useState } from "react";

import type { AssistantMode } from "../types/assistant";

export const ASSISTANT_MODE_KEY = "ocean.assistantMode";

const ASSISTANT_MODES = new Set<AssistantMode>([
  "off",
  "assisted",
  "guided",
  "supervisor",
]);

export function useAssistantMode() {
  const [mode, setModeState] = useState<AssistantMode>(readAssistantMode);

  const setMode = useCallback((nextMode: AssistantMode) => {
    const safeMode = ASSISTANT_MODES.has(nextMode) ? nextMode : "assisted";
    setModeState(safeMode);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ASSISTANT_MODE_KEY, safeMode);
    }
  }, []);

  return { mode, setMode };
}

function readAssistantMode(): AssistantMode {
  if (typeof window === "undefined") return "assisted";
  const storedMode = window.localStorage.getItem(ASSISTANT_MODE_KEY);
  return storedMode && ASSISTANT_MODES.has(storedMode as AssistantMode)
    ? storedMode as AssistantMode
    : "assisted";
}
