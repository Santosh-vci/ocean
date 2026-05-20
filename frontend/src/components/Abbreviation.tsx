import { Fragment, type ReactNode } from "react";

const ABBREVIATIONS: Record<string, string> = {
  ABL: "Andhika Bahtera Line",
  AIS: "Automatic Identification System",
  AVAIL: "Available",
  AVG: "Average",
  AUTH: "Authorization",
  CALC: "Calculation",
  CSV: "Comma-separated values",
  CTS: "Cargo Transfer Ship / transshipment asset",
  ETA: "Estimated Time of Arrival",
  ETB: "Estimated Time of Berthing",
  ETC: "Estimated Time of Completion",
  FC: "Floating Crane",
  FTS: "Floating Transfer Station",
  GPS: "Global Positioning System",
  ID: "Identifier",
  IP: "Internet Protocol",
  JSON: "JavaScript Object Notation",
  KB: "Kilobytes",
  KCAL: "Kilocalories",
  KM: "Kilometres",
  MB: "Megabytes",
  MT: "Metric tonnes",
  MVP: "Minimum Viable Product",
  OGV: "Ocean Going Vessel",
  OGVS: "Ocean Going Vessels",
  PLC: "Programmable Logic Controller",
  PLN: "Planned",
  POS: "Position",
  PRD: "Predicted",
  QC: "Quality Control",
  RBAC: "Role-Based Access Control",
  REQ: "Required",
  SIM: "Simulation",
  TPH: "Tonnes per hour",
  URL: "Uniform Resource Locator",
};

const TOKEN_PATTERN = /\b(ABL|AIS|AVAIL|AVG|AUTH|CALC|CSV|CTS|ETA|ETB|ETC|FC|FTS|GPS|ID|IP|JSON|KB|KCAL|KM|MB|MT|MVP|OGVS?|PLC|PLN|POS|PRD|QC|RBAC|REQ|SIM|TPH|URL)\b/gi;

type AbbrProps = {
  children?: ReactNode;
  term: string;
};

export function Abbr({ children, term }: AbbrProps) {
  const expansion = ABBREVIATIONS[term.toUpperCase()] ?? term;

  return (
    <abbr
      aria-label={`${children ?? term}: ${expansion}`}
      className="abbreviation-tooltip"
      title={expansion}
    >
      {children ?? term}
    </abbr>
  );
}

export function expandAbbreviationsText(text: string) {
  return text.replace(TOKEN_PATTERN, (token) => {
    const expansion = ABBREVIATIONS[token.toUpperCase()];
    return expansion ? `${token} (${expansion})` : token;
  });
}

export function AbbrText({ text }: { text: string }) {
  const parts = text.split(TOKEN_PATTERN);

  return (
    <>
      {parts.map((part, index) => {
        const expansion = ABBREVIATIONS[part.toUpperCase()];
        if (!expansion) return <Fragment key={`${part}-${index}`}>{part}</Fragment>;
        return <Abbr key={`${part}-${index}`} term={part}>{part}</Abbr>;
      })}
    </>
  );
}
