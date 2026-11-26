/**
 * Tailwind CSS 主题配置
 * 定义清透风格的颜色、字体、阴影和动效
 */
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Inter"',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', "Consolas", "monospace"],
      },
      colors: {
        canvas: "#FAFBFF",
        surface: "#FFFFFF",
        line: "#E9EBF5",
        ink: "#171A26",
        muted: "#8B91A7",
        brand: "#4D6BFE",
        brandDeep: "#3B55E0",
        brandSoft: "#EEF1FF",
        success: "#0FA97F",
        danger: "#E5484D",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(23, 26, 38, 0.04), 0 6px 20px -8px rgba(23, 26, 38, 0.12)",
        float: "0 8px 30px -12px rgba(23, 26, 38, 0.18), 0 2px 8px rgba(23, 26, 38, 0.04)",
      },
      keyframes: {
        "pop-in": {
          "0%": { opacity: "0", transform: "translateY(8px) scale(0.97)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pop-in": "pop-in 180ms cubic-bezier(0.16, 1, 0.3, 1)",
        "fade-in": "fade-in 240ms ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
