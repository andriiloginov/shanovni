module.exports = {
  plugins: [ // <--- ЗМІНЕНО ТУТ! Це масив плагінів!
    require('@tailwindcss/postcss')({}), // <--- ТУТ ВЖЕ БЕЗ КЛЮЧА
    require('autoprefixer'), // <--- ТУТ ТЕЖ ЗМІНЕНО!
  ],
}