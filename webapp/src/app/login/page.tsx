import Image from "next/image";
import { Alert } from "@/components/Alert";
import { Field } from "@/components/form";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";

const APP = process.env.NEXT_PUBLIC_APP_NAME ?? "Kling Account Maker";
export const metadata = { title: `Masuk — ${APP}` };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; next?: string }>;
}) {
  const { error, next } = await searchParams;
  return (
    <main className="login">
      <header className="login-bar">
        <span className="login-brand">
          <Image src="/logo/kling-icon.svg" alt="Kling Account Maker" width={36} height={36} priority />
          {APP}
        </span>
        <ThemeToggle />
      </header>

      <div className="login-main">
        <form method="post" action="/api/auth/login" className="login-card">
          <input type="hidden" name="next" value={next ?? "/"} />
          <div className="login-head">
            <Image src="/logo/kling-icon.svg" alt="" width={72} height={72} className="login-logo" />
            <h1 className="h5">Masuk ke Console</h1>
            <p className="caption text-text2">Akses dashboard khusus tim internal.</p>
          </div>

          {error && <Alert tone="err">Username atau password salah.</Alert>}

          <Field label="Username" icon="person">
            <input name="user" autoComplete="username" required autoFocus className="input lg" />
          </Field>
          <Field label="Password" icon="lock">
            <input name="password" type="password" autoComplete="current-password" required className="input lg" />
          </Field>

          <button type="submit" className="btn primary lg full">
            <Icon name="login" />
            Masuk
          </button>
        </form>
      </div>

      <footer className="login-bar foot">
        <span>Kurma Group · Kling Account Maker</span>
      </footer>
    </main>
  );
}
