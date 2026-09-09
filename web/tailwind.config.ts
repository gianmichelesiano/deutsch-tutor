import type { Config } from "tailwindcss";

// Token estratti da design/Deutsch-Tutor.dc.html (piano v1.1, sezione 0.1).
// Non re-inventare colori: usare questi token.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        page: "#EDE6D6",
        surface: "#F6F1E7",
        card: "#FFFFFF",
        border: { DEFAULT: "#E7DFD0", strong: "#D8CFBD" },
        primary: "#22281F",
        secondary: "#6E6559",
        muted: "#8A8072",
        faint: "#A79E8E",
        ink: "#2A3324",
        accent: "#5F8B7A",
        // Badge stato vocabolo
        vocab: {
          new: "#8A6A2E",
          "new-bg": "#EFE6D8",
          seen: "#55694A",
          "seen-bg": "#E9EFE3",
          used: "#2E6B58",
          "used-bg": "#E3EEEA",
          consolidated: "#F6F1E7",
          "consolidated-bg": "#2A3324",
        },
        // Tag origine parola (harvest)
        src: {
          requested: "#8A6A2E",
          "requested-bg": "#EFE6D8",
          error: "#A0452E",
          "error-bg": "#F3E3DE",
          agent: "#2E6B58",
          "agent-bg": "#E3EEEA",
        },
      },
      fontFamily: {
        serif: ["var(--font-newsreader)", "Newsreader", "serif"],
        sans: ["var(--font-work-sans)", "Work Sans", "sans-serif"],
      },
      borderRadius: {
        card: "16px",
        btn: "12px",
        pill: "20px",
      },
    },
  },
  plugins: [],
};

export default config;
