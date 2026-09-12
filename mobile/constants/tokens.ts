// Semantic values only: do not share Tailwind class names with the web client.
export const tokens = {
  color: { background: "#f7f8fa", surface: "#ffffff", text: "#111827", muted: "#667085", border: "#e5e7eb", primary: "#111827", danger: "#b42318" },
  spacing: { xs: 6, sm: 10, md: 14, lg: 20, xl: 28 },
  radius: { card: 14, control: 12 },
  touchTarget: 48,
  typography: { title: 28, body: 16, detail: 14 }
} as const;
