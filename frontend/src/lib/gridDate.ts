const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export type GridDateParts = {
  dateLine: string;
  timeLine: string;
};

export function formatGridDateParts(value: string | null | undefined): GridDateParts | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const day = String(date.getDate()).padStart(2, "0");
  const month = MONTHS[date.getMonth()];
  const year = String(date.getFullYear()).slice(-2);
  const weekday = WEEKDAYS[date.getDay()];
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return {
    dateLine: `${day} ${month}'${year}`,
    timeLine: `${weekday} ${hour}:${minute}`,
  };
}

export function formatGridDateLabel(value: string | null | undefined, fallback = "-") {
  const parts = formatGridDateParts(value);
  if (!parts) return fallback;
  return `${parts.dateLine} ${parts.timeLine}`;
}
