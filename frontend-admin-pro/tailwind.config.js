/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,vue}"],
  theme: {
    container: {
      center: true,
    },
    extend: {
      colors: {
        admin: {
          page: "var(--admin-page-bg, #fafafa)",
          primary: "var(--el-color-primary, #409eff)",
          muted: "var(--el-text-color-placeholder, #909399)",
        },
        tv: {
          bg: "#0f0f1a",
          card: "#1a1a2e",
          border: "#2a2a3e",
          text: "#e2e8f0",
          muted: "#64748b",
          green: "#22c55e",
          red: "#ef4444",
          amber: "#f59e0b",
          sky: "#38bdf8",
          emerald: "#34d399",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.04)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.08)",
      },
    },
  },
  plugins: [],
}
