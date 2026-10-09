/** @type {import('tailwindcss').Config} */
export default {
  mode: 'jit', // Enable JIT mode if needed
  content: [],
  theme: {
    fontFamily: {
      'sans': ["Open Sans", 'sans-serif'],
    },
    fontSize: {
      'xs': '0.65rem',  // Modifica la mida de la font per a la classe 'text-xs'
      'sm': '0.75rem', // Modifica la mida de la font per a la classe 'text-sm'
      'base': '0.80rem',   // Modifica la mida de la font per a la classe 'text-base'
      'lg': '1rem', // Modifica la mida de la font per a la classe 'text-lg'
      'xl': '1.125rem',  // Modifica la mida de la font per a la classe 'text-xl'
      '2xl': '1.25rem',  // Modifica la mida de la font per a la classe 'text-2xl'
      '3xl': '1.5rem',  // Modifica la mida de la font per a la classe 'text-3xl'
      '4xl': '1.875rem',   // Modifica la mida de la font per a la classe 'text-4xl'
      '5xl': '2.25rem',      // Modifica la mida de la font per a la classe 'text-5xl'
      '6xl': '3rem',      // Modifica la mida de la font per a la classe 'text-6xl'
      '7xl': '4rem',      // Modifica la mida de la font per a la classe 'text-7xl'
      '8xl': '5rem',      // Modifica la mida de la font per a la classe 'text-8xl'
      '9xl': '7rem',      // Modifica la mida de la font per a la classe 'text-9xl'
    },
    extend: {
      keyframes: {
        'stats-box-ping': {
          '0%': {
            boxShadow: '0 0 0 0 rgba(14, 165, 233, 0.45)',
            borderColor: 'rgb(14, 165, 233)',
          },
          '70%': {
            boxShadow: '0 0 0 8px rgba(14, 165, 233, 0)',
            borderColor: 'rgb(229, 231, 235)',
          },
          '100%': {
            boxShadow: '0 0 0 0 rgba(14, 165, 233, 0)',
            borderColor: 'rgb(229, 231, 235)',
          },
        },
      },
      animation: {
        'stats-box-ping': 'stats-box-ping 0.6s ease-out 2',
      },
    },
  },
  plugins: [],
}

