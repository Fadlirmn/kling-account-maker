"use client";

import { useEffect, useState } from "react";
import { Avatar, Button, Card, Loading, PageBar, Pill } from "@/components/ui";
import { Field } from "@/components/form";
import { Alert, FlashMsg } from "@/components/Alert";
import { useConfirm } from "@/components/Dialog";
import { fmtDateTime, type UsersResponse } from "@/lib/api";

async function call(method: string, path: string, body?: unknown): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(path, {
      method,
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    if (res.ok) return { ok: true };
    const j = await res.json().catch(() => null);
    return { ok: false, error: typeof j?.detail === "string" ? j.detail : "Permintaan gagal" };
  } catch {
    return { ok: false, error: "Server tidak dapat dihubungi" };
  }
}

export default function UsersSettingsPage() {
  const confirm = useConfirm();
  const [data, setData] = useState<UsersResponse | null | undefined>(undefined);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [resetFor, setResetFor] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = () =>
    fetch("/api/users", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));

  useEffect(() => {
    load();
  }, []);

  const flash = (ok: boolean, text: string) => {
    setMsg({ ok, text });
    setTimeout(() => setMsg(null), 5000);
  };

  const run = async (action: () => Promise<{ ok: boolean; error?: string }>, okText: string) => {
    setBusy(true);
    const r = await action();
    setBusy(false);
    flash(r.ok, r.ok ? okText : r.error ?? "Gagal");
    if (r.ok) await load();
    return r.ok;
  };

  const addUser = async () => {
    if (await run(() => call("POST", "/api/users", { username: username.trim(), password }), `User ${username.trim()} ditambahkan`)) {
      setUsername("");
      setPassword("");
    }
  };

  const resetPassword = async (id: number, name: string) => {
    if (await run(() => call("PUT", `/api/users/${id}`, { password: newPassword }), `Password ${name} diganti`)) {
      setResetFor(null);
      setNewPassword("");
    }
  };

  const removeUser = async (id: number, name: string) => {
    const ok = await confirm({
      title: `Hapus user “${name}”?`,
      body: "Sesi login user ini langsung berakhir. Tindakan tidak bisa dibatalkan.",
      confirmLabel: "Hapus",
      danger: true,
    });
    if (!ok) return;
    run(() => call("DELETE", `/api/users/${id}`), `User ${name} dihapus`);
  };

  if (data === undefined) return <Loading />;
  if (data === null) return <Alert tone="err" title="Daftar user tidak bisa dimuat">Backend tidak dapat dihubungi.</Alert>;

  return (
    <div className="max-w-[760px] w-full mx-auto flex flex-col gap-4">
      <PageBar meta={`Login sebagai ${data.me}`} />
      <FlashMsg msg={msg} />

      <Card title="Akun Dashboard" desc="Semua akun punya akses penuh">
        <ul className="divide-y divide-line-soft">
          {data.env_admin && (
            <li className="flex items-center gap-3 py-3">
              <Avatar name={data.env_admin} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 body2 text-text font-semibold">
                  <span className="truncate">{data.env_admin}</span>
                  <Pill sm>env</Pill>
                  {data.me_is_env_admin && <Pill tone="violet" sm>kamu</Pill>}
                </div>
                <div className="caption text-text3">Akun cadangan · ubah lewat deploy/init-user.sh</div>
              </div>
            </li>
          )}
          {data.users.map((u) => {
            const self = u.username === data.me;
            const resetting = resetFor === u.id;
            return (
              <li key={u.id} className="py-3 flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <Avatar name={u.username} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 body2 text-text font-semibold">
                      <span className="truncate">{u.username}</span>
                      {self && <Pill tone="violet" sm>kamu</Pill>}
                    </div>
                    <div className="caption text-text3">dibuat {fmtDateTime(u.created_at)}</div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button variant="text" size="sm" icon="key" onClick={() => { setResetFor(resetting ? null : u.id); setNewPassword(""); }}>
                      <span className="hidden sm:inline">Password</span>
                    </Button>
                    {!self && (
                      <Button variant="danger-text" size="sm" icon="delete" disabled={busy} onClick={() => removeUser(u.id, u.username)}>
                        <span className="hidden sm:inline">Hapus</span>
                      </Button>
                    )}
                  </div>
                </div>
                {resetting && (
                  <div className="flex flex-col sm:flex-row gap-2 sm:pl-[46px]">
                    <input type="password" autoComplete="new-password" className="input" placeholder="Password baru (min. 8 karakter)"
                      value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                    <Button variant="primary" disabled={busy || newPassword.length < 8} onClick={() => resetPassword(u.id, u.username)}>Simpan</Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
        {data.users.length === 0 && <p className="caption text-text3 mt-2">Belum ada user tambahan.</p>}
      </Card>

      <Card title="Tambah User" desc="Username 3–32 karakter (huruf, angka, . _ -) · password min. 8 karakter">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!busy && username.trim().length >= 3 && password.length >= 8) addUser();
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
            <Field label="Username">
              <input className="input" autoComplete="off" value={username} onChange={(e) => setUsername(e.target.value)} />
            </Field>
            <Field label="Password">
              <input type="password" autoComplete="new-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
          </div>
          <div className="card-actions">
            <Button type="submit" variant="primary" icon="person_add" disabled={busy || username.trim().length < 3 || password.length < 8}>
              {busy ? "Memproses…" : "Tambah User"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
