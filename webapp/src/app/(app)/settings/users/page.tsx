"use client";

import { useEffect, useState } from "react";
import { Avatar, Button, Card, Loading, PageBar, Pill } from "@/components/ui";
import { Dialog } from "@/components/Dialog";
import { Select } from "@/components/form";
import type { DashboardUser, UserRole } from "@/lib/api";
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

// Divisi = akhiran username (<nama>_<divisi>), sama dengan seed intercept-google-flow.
const DIVISIONS: { id: string; label: string }[] = [
  { id: "herbal", label: "Divisi Herbal" },
  { id: "fashion_malaysia", label: "Divisi Fashion Malaysia" },
  { id: "fashion_filipina", label: "Divisi Fashion Filipina" },
  { id: "operasional", label: "Divisi Operasional" },
];
const OTHER = { id: "", label: "Lainnya" };

function divisionOf(username: string): string {
  const d = DIVISIONS.find((x) => username.endsWith(`_${x.id}`));
  return d ? d.id : "";
}
function displayName(username: string): string {
  const d = divisionOf(username);
  const base = d ? username.slice(0, -(d.length + 1)) : username;
  return base.charAt(0).toUpperCase() + base.slice(1);
}
const ROLE_LABEL: Record<UserRole, string> = { admin: "Admin", member: "Member" };

/** Admin tanpa akhiran divisi (mis. hereacil) → kartu Admin bersama admin env. */
function adminsWithoutDivision(users: DashboardUser[]) {
  return users.filter((u) => u.role === "admin" && !divisionOf(u.username)).sort((a, b) => a.username.localeCompare(b.username));
}

function groupByDivision(users: DashboardUser[]) {
  const groups = [...DIVISIONS, OTHER].map((d) => ({ ...d, users: [] as DashboardUser[] }));
  for (const u of users) {
    const d = divisionOf(u.username);
    if (!d && u.role === "admin") continue;   // admin tanpa divisi tampil di kartu Admin
    const g = groups.find((x) => x.id === d) ?? groups[groups.length - 1];
    g.users.push(u);
  }
  // admin di atas, lalu member; masing-masing urut nama
  for (const g of groups) g.users.sort((a, b) => (a.role === b.role ? a.username.localeCompare(b.username) : a.role === "admin" ? -1 : 1));
  return groups.filter((g) => g.users.length > 0);
}

export default function UsersSettingsPage() {
  const confirm = useConfirm();
  const [data, setData] = useState<UsersResponse | null | undefined>(undefined);
  const [username, setUsername] = useState("");          // nama (tanpa akhiran divisi)
  const [division, setDivision] = useState(DIVISIONS[0].id);
  const [password, setPassword] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [role, setRole] = useState<UserRole>("member");
  const [resetFor, setResetFor] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fullUsername = `${username.trim().toLowerCase().replace(/\s+/g, "")}${division ? `_${division}` : ""}`;
  const canAdd = !busy && username.trim().length >= 2 && fullUsername.length >= 3 && password.length >= 8;

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
    if (await run(() => call("POST", "/api/users", { username: fullUsername, password, role }), `User ${fullUsername} ditambahkan`)) {
      setUsername("");
      setPassword("");
      setAddOpen(false);
    }
  };

  const changeRole = async (u: DashboardUser) => {
    const next: UserRole = u.role === "admin" ? "member" : "admin";
    run(() => call("PUT", `/api/users/${u.id}`, { role: next }), `${displayName(u.username)} → ${next}`);
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


  // satu baris user (dipakai kartu Admin dan tiap divisi)
  const UserRow = ({ u }: { u: DashboardUser }) => {
    const self = u.username === data.me;
    const resetting = resetFor === u.id;
    return (
<li className="py-2.5 flex flex-col gap-3">
                  <div className="flex items-center gap-3">
                    <Avatar name={displayName(u.username)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 body2 text-text font-semibold">
                        <span className="truncate">{displayName(u.username)}</span>
                        <Pill sm tone={u.role === "admin" ? "info" : "neutral"}>{ROLE_LABEL[u.role] ?? u.role}</Pill>
                        {self && <Pill tone="violet" sm>kamu</Pill>}
                      </div>
                      <div className="caption text-text3 truncate"><span className="font-mono">{u.username}</span> · dibuat {fmtDateTime(u.created_at)}</div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      {!self && (
                        <Button variant="text" size="sm" icon={u.role === "admin" ? "person_remove" : "admin_panel_settings"} disabled={busy} onClick={() => changeRole(u)} title={u.role === "admin" ? "Jadikan member" : "Jadikan admin"}>
                          <span className="hidden md:inline">{u.role === "admin" ? "Member" : "Admin"}</span>
                        </Button>
                      )}
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
  };

  return (
    <div className="max-w-[760px] w-full mx-auto flex flex-col gap-4">
      <PageBar
        meta={`Login sebagai ${data.me} · ${data.users.length} user${data.env_admin ? " + admin env" : ""}`}
        right={<Button variant="primary" size="sm" icon="person_add" onClick={() => setAddOpen(true)}>Tambah User</Button>}
      />
      <FlashMsg msg={msg} />

      {(data.env_admin || adminsWithoutDivision(data.users).length > 0) && (
        <Card title="Admin" desc="Akses penuh · admin env dari .env, lainnya dari tabel users" padSm>
          <ul className="divide-y divide-line-soft">
            {data.env_admin && (
              <li className="flex items-center gap-3 py-2.5">
                <Avatar name={data.env_admin} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 body2 text-text font-semibold">
                    <span className="truncate">{data.env_admin}</span>
                    <Pill sm tone="info">Admin</Pill>
                    <Pill sm>env</Pill>
                    {data.me_is_env_admin && <Pill tone="violet" sm>kamu</Pill>}
                  </div>
                  <div className="caption text-text3">Akun cadangan · ubah lewat deploy/init-user.sh</div>
                </div>
              </li>
            )}
            {adminsWithoutDivision(data.users).map((u) => (
              <UserRow key={u.id} u={u} />
            ))}
          </ul>
        </Card>
      )}

      {groupByDivision(data.users).map((g) => (
        <Card key={g.id || "lainnya"} title={g.label} desc={`${g.users.filter((u) => u.role === "admin").length} admin · ${g.users.filter((u) => u.role !== "admin").length} member`} padSm>
          <ul className="divide-y divide-line-soft">
            {g.users.map((u) => <UserRow key={u.id} u={u} />)}
          </ul>
        </Card>
      ))}
      {data.users.length === 0 && <Card><p className="caption text-text3">Belum ada user tambahan. Klik “Tambah User”.</p></Card>}

      <Dialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Tambah User"
        block
        actions={
          <>
            <Button variant="text" onClick={() => setAddOpen(false)}>Batal</Button>
            <Button variant="primary" icon="person_add" disabled={!canAdd} onClick={addUser}>{busy ? "Memproses…" : "Tambah"}</Button>
          </>
        }
      >
        <form onSubmit={(e) => { e.preventDefault(); if (canAdd) addUser(); }} className="flex flex-col gap-3.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
            <Field label="Nama" hint="huruf/angka, tanpa spasi">
              <input className="input" autoComplete="off" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="mis. rian" />
            </Field>
            <Field label="Divisi">
              <Select value={division} onChange={(e) => setDivision(e.target.value)}>
                {DIVISIONS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
                <option value="">Tanpa divisi</option>
              </Select>
            </Field>
            <Field label="Role">
              <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </Select>
            </Field>
            <Field label="Password" hint="min. 8 karakter">
              <input type="password" autoComplete="new-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
          </div>
          <p className="caption text-text3">Username: <span className="font-mono text-text">{fullUsername || "—"}</span></p>
        </form>
      </Dialog>
    </div>
  );
}
