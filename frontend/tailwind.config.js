/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAF9F5",
        surface: "#FFFFFF",
        ink: "#141413",
        muted: "#5E5D59",
        line: "#E8E6DC",
        chip: { DEFAULT: "#F0EEE6", ink: "#3D3D3A" },
        accent: "#D97757",
      },
      fontFamily: {
        serif: ["Lora", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
