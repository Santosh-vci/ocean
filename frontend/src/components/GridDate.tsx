import { formatGridDateParts } from "../lib/gridDate";

type GridDateProps = {
  className?: string;
  fallback?: string;
  value: string | null | undefined;
};

export function GridDate({ className, fallback = "-", value }: GridDateProps) {
  const parts = formatGridDateParts(value);
  const classes = ["grid-date", className].filter(Boolean).join(" ");

  if (!parts) {
    return <span className={`${classes} is-empty`}>{fallback}</span>;
  }

  return (
    <time className={classes} dateTime={value ?? undefined}>
      <span>{parts.dateLine}</span>
      <em>{parts.timeLine}</em>
    </time>
  );
}
