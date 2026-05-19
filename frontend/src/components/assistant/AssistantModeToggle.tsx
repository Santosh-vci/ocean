import type { AssistantMode } from "../../types/assistant";

type AssistantModeToggleProps = {
  mode: AssistantMode;
  onChange: (mode: AssistantMode) => void;
};

const MODES: Array<{ value: AssistantMode; label: string }> = [
  { value: "assisted", label: "Assist" },
  { value: "guided", label: "Guide" },
  { value: "supervisor", label: "Super" },
  { value: "off", label: "Off" },
];

function modeTitle(mode: AssistantMode) {
  if (mode === "guided") return "Assistant mode: guided preview";
  return `Assistant mode: ${mode}`;
}

export function AssistantModeToggle({ mode, onChange }: AssistantModeToggleProps) {
  return (
    <div aria-label="Assistant mode" className="assistant-mode-toggle" role="group">
      {MODES.map((item) => (
        <button
          aria-pressed={mode === item.value}
          className={mode === item.value ? "active" : ""}
          key={item.value}
          onClick={() => onChange(item.value)}
          title={modeTitle(item.value)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
