/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./*.html",
    "./public/**/*.html",
  ],
  theme: {
    extend: {}, 
  },
  plugins: [
    require('daisyui'),
  ],
  daisyui: {
    themes: ["light", "dark", "cupcake", "bumblebee"],
  },
};