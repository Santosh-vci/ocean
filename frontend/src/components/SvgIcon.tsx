import opsIcons from "../assets/ops-icons.svg";
import type { IconName } from "../lib/navigation";

type SvgIconProps = {
  name: IconName;
  className?: string;
  title?: string;
};

export function SvgIcon({ name, className = "svg-icon", title }: SvgIconProps) {
  return (
    <svg aria-hidden={title ? undefined : true} className={className} role={title ? "img" : undefined}>
      {title ? <title>{title}</title> : null}
      <use href={`${opsIcons}#icon-${name}`} />
    </svg>
  );
}
