/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{vue,ts,tsx,js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
      colors: {
        surface: 'var(--panel)',
        bg: 'var(--bg)',
        border: 'var(--border)',
        text: 'var(--text)',
        muted: 'var(--muted)',
        danger: {
          DEFAULT: 'var(--state-error-border)',
          bg: 'var(--state-error-bg)',
        },
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
      },
      spacing: {
        2: 'var(--space-2)',
        3: 'var(--space-3)',
        4: 'var(--space-4)',
        6: 'var(--space-6)',
      },
      boxShadow: {
        focus: 'var(--focus-ring)',
      },
    },
  },
  plugins: [],
};
