/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        "risk-red": "#dc2626",
        "risk-yellow": "#fbbf24",
        "risk-green": "#34d399",
        surface: "#0f172a",
        border: "rgba(255,255,255,0.07)",
      },
    },
  },
  plugins: [],
};
