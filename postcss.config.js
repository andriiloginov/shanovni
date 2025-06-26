module.exports = {
  plugins: [ // <--- Масив плагінів!
    require('@tailwindcss/postcss')({}), // <--- Без ключа
    require('autoprefixer'), // <--- Автофіксер
  ],
}