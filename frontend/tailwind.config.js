/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#2563EB', light: '#EFF6FF', dark: '#1D4ED8' },
      },
    },
  },
  plugins: [],
}
