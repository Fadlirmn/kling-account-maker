import type { Config } from "tailwindcss";
import defaultTheme from "tailwindcss/defaultTheme";

/**
 * Tema: Kurma web — Material 3 tonal surface (coral primary / violet secondary / indigo nav).
 * Semua warna menunjuk CSS variable di globals.css (:root terang, [data-theme="dark"] gelap),
 * jadi satu kelas Tailwind otomatis ikut skema. Catatan: alpha modifier (bg-x/10) tidak berlaku
 * untuk warna var(); pakai token khusus (state-hover, nav-hover, backdrop).
 * Font: Plus Jakarta Sans (next/font) + Material Symbols Outlined (<link> di layout.tsx).
 */
const v = (name: string) => `var(--${name})`;

const tokens = [
  "bg", "paper", "surface-lowest", "surface-low", "surface-container", "surface-high", "surface-highest",
  "surface-variant", "on-surface-variant", "line-soft",
  "text", "text2", "text3", "divider", "outline",
  "primary", "primary-hover", "on-primary", "primary-container", "on-primary-container",
  "secondary", "on-secondary", "secondary-container", "on-secondary-container",
  "success", "success-container", "on-success-container",
  "warn", "warn-container", "on-warn-container",
  "err", "err-container", "on-err-container",
  "info", "info-container", "on-info-container",
  "chip-bg", "chip-fg",
  "brand", "brand-soft", "nav-bg", "nav-fg", "nav-fg-muted", "nav-section", "nav-active-bg", "nav-active-fg",
  "nav-hover", "nav-pressed", "nav-divider",
  "state-hover", "state-selected", "backdrop", "avatar-2", "on-avatar",
] as const;

const colors: Record<string, string> = Object.fromEntries(tokens.map((t) => [t, v(t)]));

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors,
      fontFamily: {
        sans: ["var(--font-jakarta)", "Plus Jakarta Sans", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "10px",
        DEFAULT: "10px",
        md: "12px",
        lg: "14px",
        xl: "16px",
        "2xl": "18px",
      },
      boxShadow: {
        card: "var(--shadow)",
        hover: "var(--shadow-hover)",
        lg: "var(--shadow-lg)",
      },
      maxWidth: {
        content: "1080px",
      },
      spacing: {
        sidebar: "248px",
        header: "72px",
      },
      screens: {
        ...defaultTheme.screens,
        shell: "861px",
      },
    },
  },
  plugins: [],
};

export default config;
