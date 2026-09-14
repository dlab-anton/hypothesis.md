/** @type {import('tailwindcss').Config} */
const config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  future: {
    // Use the default CSS processor instead of lightningcss
    // This might help with the Windows compatibility issue
    lightningcss: false,
  },
  theme: {
    extend: {},
  },
  plugins: [],
}

export default config
