/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        // Dark theme colors (from original CSS)
        primary: {
          DEFAULT: '#6366f1',
          hover: '#818cf8',
          light: '#a5b4fc',
        },
        accent: {
          DEFAULT: '#22d3ee',
          hover: '#67e8f9',
        },
        surface: {
          DEFAULT: '#1e1e2e',
          elevated: '#2a2a3e',
          hover: '#3a3a4e',
        },
        background: '#0f0f1a',
        text: {
          DEFAULT: '#e2e8f0',
          muted: '#94a3b8',
          dim: '#64748b',
        },
        border: {
          DEFAULT: 'rgba(255, 255, 255, 0.1)',
          hover: 'rgba(255, 255, 255, 0.2)',
        },
        success: {
          DEFAULT: '#22c55e',
          bg: 'rgba(34, 197, 94, 0.1)',
        },
        warning: {
          DEFAULT: '#f59e0b',
          bg: 'rgba(245, 158, 11, 0.1)',
        },
        danger: {
          DEFAULT: '#ef4444',
          bg: 'rgba(239, 68, 68, 0.1)',
        },
      },
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-20px)' },
        },
      },
      boxShadow: {
        'glow': '0 0 20px rgba(99, 102, 241, 0.3)',
        'glow-lg': '0 0 40px rgba(99, 102, 241, 0.4)',
      },
    },
  },
  plugins: [],
}









