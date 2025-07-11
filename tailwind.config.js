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
    themes: ["retro", "aqua", "light", "dark"], // Add your desired themes here
  },
};