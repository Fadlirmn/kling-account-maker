import { Icon } from "./Icon";

export function Empty({ what, hint, icon = "hourglass_empty" }: { what: string; hint?: string; icon?: string }) {
  return (
    <div className="empty">
      <Icon name={icon} size="xl" />
      <span>
        Data riil <span className="text-text font-semibold">{what}</span> akan tampil di sini setelah run pertama.
      </span>
      {hint && <span className="caption">{hint}</span>}
    </div>
  );
}
