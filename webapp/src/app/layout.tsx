import type { Metadata } from "next";
import "./globals.css";

// Plus Jakarta Sans via <link> (bukan next/font/google): build Docker tidak boleh bergantung
// pada fetch Google Fonts saat compile (pernah gagal: "An error occurred in `next/font`").
// Variabel --font-jakarta didefinisikan di globals.css.
const JAKARTA_FONT =
  "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap";

export const metadata: Metadata = {
  title: process.env.NEXT_PUBLIC_APP_NAME ?? "Kling Account Maker",
  description: "Dashboard pool akun standby Kling — pembuatan batch, riwayat run, dan pengaturan.",
};

// Pilih skema sebelum CSS dirender agar tidak berkedip: localStorage "theme" = light | dark | kosong = ikut sistem.
// :root = terang; gelap = data-theme="dark".
const THEME_INIT = `(function(){var d=document.documentElement;try{var m=localStorage.getItem("theme");var mode=(m==="light"||m==="dark")?m:"system";var dark=mode==="dark"||(mode==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);if(dark)d.dataset.theme="dark";d.dataset.themeMode=mode;}catch(e){d.dataset.themeMode="system";}})();`;

// Material Symbols tidak tersedia di next/font/google (Next 15.1) → via <link>, sama seperti sumber.
const MATERIAL_SYMBOLS =
  "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,400,0,0&display=block";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={JAKARTA_FONT} />
        <link rel="stylesheet" href={MATERIAL_SYMBOLS} />
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body className="bg-bg text-text font-sans antialiased">{children}</body>
    </html>
  );
}
