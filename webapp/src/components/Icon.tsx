/** Material Symbols Outlined (ligature). Nama ikon: https://fonts.google.com/icons */
export function Icon({
  name,
  size,
  fill,
  spin,
  className = "",
  title,
}: {
  name: string;
  size?: "sm" | "md" | "lg" | "xl";
  fill?: boolean;
  spin?: boolean;
  className?: string;
  title?: string;
}) {
  const cls = ["ms", size, fill ? "fill" : "", spin ? "spin" : "", className].filter(Boolean).join(" ");
  return (
    <span className={cls} aria-hidden={title ? undefined : "true"} role={title ? "img" : undefined} aria-label={title} title={title}>
      {name}
    </span>
  );
}
