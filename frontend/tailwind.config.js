/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Warm paper stack — the stationery vibe
        cream: '#FDF8F0',   // primary background
        linen: '#F9F3E8',   // secondary surface
        paper: '#FFFCF7',   // cards, elevated surfaces

        // Ink gradients — warm browns, never pure black
        ink:   '#2D2A26',   // primary text
        slate: '#6B6560',   // secondary text
        fog:   '#9E9790',   // muted / labels
        rule:  '#E8E0D4',   // borders, dividers
        mist:  '#F3ECDD',   // hover surfaces

        // Canvas stage — the flow canvas is a dark warm "stage" so edges,
        // particles and node cards can glow against it
        stage:        '#23201C',
        'stage-deep': '#1C1916',
        'stage-line': '#3B362E',

        // Semantic accents — use sparingly, only for meaning
        rose:  '#E8729A',   // alerts, count badges, attention
        sage:  '#7BC89F',   // success, connected, online
        iris:  '#9B7ED8',   // primary brand / active state
        amber: '#E8A86D',   // warning, secondary info

        // Soft siblings for hover rings
        'rose-soft':  '#F5C6D8',
        'sage-soft':  '#C5E8D5',
        'iris-soft':  '#D4C5F0',
        'amber-soft': '#F5DABC',
      },
      fontFamily: {
        sans: ['Ubuntu', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"Ubuntu Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        'sm': '8px',
        DEFAULT: '10px',
        'md': '12px',
        'lg': '14px',
        'xl': '18px',
        '2xl': '22px',
      },
      boxShadow: {
        'ink-sm': '0 2px 12px rgba(45, 42, 38, 0.06)',
        'ink':    '0 4px 20px rgba(45, 42, 38, 0.10)',
        'ink-lg': '0 8px 32px rgba(45, 42, 38, 0.14)',
      },
      letterSpacing: {
        'tightest': '-0.5px',
        'mono-wide': '1px',
        'mono-wider': '2px',
      },
      keyframes: {
        'fade-up': {
          '0%':   { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.35s ease both',
      },
    },
  },
  plugins: [
    // eslint-disable-next-line no-undef
    require('@tailwindcss/typography'),
  ],
}
