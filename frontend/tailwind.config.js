/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  // DaisyUI themes matching Homebox
  daisyui: {
    themes: [
      'light',
      'dark',
      'cupcake',
      'bumblebee',
      'emerald',
      'corporate',
      'synthwave',
      'retro',
      'cyberpunk',
      'valentine',
      'halloween',
      'garden',
      'forest',
      'aqua',
      'lofi',
      'pastel',
      'fantasy',
      'wireframe',
      'black',
      'luxury',
      'dracula',
      'cmyk',
      'autumn',
      'business',
      'acid',
      'lemonade',
      'night',
      'coffee',
      'winter',
      // Custom "homebox" theme that matches the Homebox default
      {
        homebox: {
          'primary': '#6366f1',
          'primary-content': '#ffffff',
          'secondary': '#818cf8',
          'secondary-content': '#ffffff',
          'accent': '#22d3ee',
          'accent-content': '#000000',
          'neutral': '#1e1e2e',
          'neutral-content': '#f1f5f9',
          'base-100': '#0a0a0f',
          'base-200': '#13131f',
          'base-300': '#1e1e2e',
          'base-content': '#f1f5f9',
          'info': '#3abff8',
          'info-content': '#000000',
          'success': '#10b981',
          'success-content': '#000000',
          'warning': '#f59e0b',
          'warning-content': '#000000',
          'error': '#ef4444',
          'error-content': '#ffffff',
        },
      },
    ],
    // Don't add extra base styles - we have our own
    base: true,
    // Enable styled components
    styled: true,
    // Enable utility classes
    utils: true,
    // Log to console during build
    logs: false,
  },
  theme: {
    extend: {
      colors: {
        // Primary (Indigo) - full tonal scale
        // Theme colors are applied via CSS overrides in app.css
        primary: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          DEFAULT: '#6366f1',
          hover: '#818cf8',
          light: '#a5b4fc',
        },

        // Neutral scale for backgrounds, text, and borders
        // Theme colors are applied via CSS overrides in app.css
        neutral: {
          950: '#0a0a0f',  // App background
          900: '#13131f',  // Card background
          800: '#1e1e2e',  // Elevated surface
          700: '#2a2a3e',  // Borders, hover states
          600: '#3a3a4e',  // Active borders
          500: '#64748b',  // Dim text
          400: '#94a3b8',  // Muted text
          300: '#cbd5e1',  // Secondary text
          200: '#e2e8f0',  // Body text
          100: '#f1f5f9',  // Headings
        },

        // Semantic colors with full scales
        success: {
          50: '#ecfdf5',
          100: '#d1fae5',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          900: '#064e3b',
          DEFAULT: '#10b981',
          bg: 'rgba(16, 185, 129, 0.1)',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          900: '#78350f',
          DEFAULT: '#f59e0b',
          bg: 'rgba(245, 158, 11, 0.1)',
        },
        error: {
          50: '#fef2f2',
          100: '#fee2e2',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          900: '#7f1d1d',
          DEFAULT: '#ef4444',
          bg: 'rgba(239, 68, 68, 0.1)',
        },

        // Accent color
        accent: {
          DEFAULT: '#22d3ee',
          hover: '#67e8f9',
        },
      },

      // Typography scale with line-height and letter-spacing
      fontSize: {
        'display': ['2.5rem', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '700' }],
        'h1': ['2rem', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '700' }],
        'h2': ['1.5rem', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        'h3': ['1.25rem', { lineHeight: '1.4', fontWeight: '600' }],
        'h4': ['1.125rem', { lineHeight: '1.4', fontWeight: '600' }],
        'body-lg': ['1.125rem', { lineHeight: '1.6' }],
        'body': ['1rem', { lineHeight: '1.6' }],
        'body-sm': ['0.875rem', { lineHeight: '1.5' }],
        'caption': ['0.75rem', { lineHeight: '1.4', letterSpacing: '0.01em' }],
        'xs-tight': ['0.6875rem', { lineHeight: '1.4' }],  // 11px
        'sm-tight': ['0.8125rem', { lineHeight: '1.4' }],  // 13px
        'md-tight': ['0.9375rem', { lineHeight: '1.5' }],  // 15px
        'xxs': ['0.625rem', { lineHeight: '1.2' }],  // 10px
      },

      fontFamily: {
        sans: ['Inter', 'Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },

      // Border radius scale
      borderRadius: {
        'lg': '0.75rem',   // 12px - inputs, small cards
        'xl': '1rem',      // 16px - buttons, medium cards
        '2xl': '1.25rem',  // 20px - large cards, modals
        '3xl': '1.5rem',   // 24px - hero elements
        '4xl': '1.75rem',  // 28px - extra large
        'pill': '0.875rem',  // 14px - pill shapes
      },

      // Extended spacing scale
      spacing: {
        '4.5': '1.125rem',  // 18px
        '5.5': '1.375rem',  // 22px
        '7.5': '1.875rem',  // 30px
        '8.5': '2.125rem',  // 34px
        '11': '2.75rem',    // 44px
        'touch': '2.75rem', // 44px - iOS minimum touch target
      },

      // Min-height scale
      minHeight: {
        'touch': '2.75rem', // 44px - iOS minimum touch target
      },

      // Min-width scale
      minWidth: {
        'touch': '2.75rem', // 44px - iOS minimum touch target
      },

      // Z-index scale for layering
      zIndex: {
        'modal': '60',
        'overlay': '100',
      },

      // Refined shadows for dark mode
      boxShadow: {
        'sm': '0 0 0 1px rgba(255, 255, 255, 0.05)',
        'DEFAULT': '0 1px 2px 0 rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.05)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.05)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.05)',
        'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.08)',
        // Primary color glow effects (coupled to primary-500: #6366f1)
        'glow': '0 0 20px rgba(99, 102, 241, 0.3)',
        'glow-lg': '0 0 40px rgba(99, 102, 241, 0.4)',
        // Semantic glow effects for interactive elements
        'primary-glow-sm': '0 2px 8px rgba(99, 102, 241, 0.3)',
        'primary-glow': '0 3px 10px rgba(99, 102, 241, 0.35)',
        'primary-ring': '0 0 0 2px rgba(99, 102, 241, 0.15)',
        'error-glow-sm': '0 2px 6px rgba(239, 68, 68, 0.25)',
        'error-glow': '0 3px 10px rgba(239, 68, 68, 0.35)',
        'success-glow': '0 0 12px rgba(34, 197, 94, 0.5)',
        'warning-glow': '0 0 8px 4px rgba(245, 158, 11, 0.25)',
      },

      // Animation system
      animation: {
        'fade-in': 'fadeIn 0.25s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
        'slide-down': 'slideDown 0.25s ease-out',
        'scale-in': 'scaleIn 0.15s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        // Component-specific animations
        'pop': 'pop 300ms ease-out',
        'typing-dot': 'dotPulse 1.4s infinite ease-in-out both',
        'stream-glow': 'pulse-glow 2s ease-in-out infinite',
        'toast-in': 'toastSlideDown 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        'toast-out': 'toastFadeOut 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards',
        'progress-shrink': 'progressShrink var(--duration, 4000ms) linear forwards',
        // Consolidated animations (moved from app.css)
        'draw-check': 'drawCheck 0.4s ease-out 0.2s forwards',
        'scale-up': 'scaleUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        'fade-slide-in': 'fadeSlideIn 0.3s ease-out forwards',
        // Approval badge pulse (moved from ChatMessage.svelte)
        'approval-pulse': 'approvalPulse 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        // Component-specific keyframes
        pop: {
          '0%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.03)' },
          '100%': { transform: 'scale(1)' },
        },
        dotPulse: {
          '0%, 80%, 100%': { transform: 'scale(0)' },
          '40%': { transform: 'scale(1)' },
        },
        // Primary color glow pulse (coupled to primary-500: #6366f1)
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 1px rgba(99, 102, 241, 0.3)' },
          '50%': { boxShadow: '0 0 12px 2px rgba(99, 102, 241, 0.4)' },
        },
        toastSlideDown: {
          from: { opacity: '0', transform: 'translateY(-100%) scale(0.95)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        toastFadeOut: {
          from: { opacity: '1', transform: 'translateY(0) scale(1)' },
          to: { opacity: '0', transform: 'translateY(-100%) scale(0.95)' },
        },
        progressShrink: {
          from: { width: '100%' },
          to: { width: '0%' },
        },
        // Consolidated keyframes (moved from app.css)
        drawCheck: {
          to: { strokeDashoffset: '0' },
        },
        scaleUp: {
          to: { transform: 'scale(1)' },
        },
        fadeSlideIn: {
          from: { opacity: '0', transform: 'translateX(-50%) translateY(10px)' },
          to: { opacity: '1', transform: 'translateX(-50%) translateY(0)' },
        },
        // Approval badge pulse (moved from ChatMessage.svelte, coupled to warning-500: #f59e0b)
        approvalPulse: {
          '0%, 100%': {
            boxShadow: '0 0 0 0 rgba(245, 158, 11, 0.4)',
            transform: 'scale(1)',
            borderColor: 'rgba(245, 158, 11, 0.4)',
          },
          '50%': {
            boxShadow: '0 0 8px 4px rgba(245, 158, 11, 0.25)',
            transform: 'scale(1.02)',
            borderColor: 'rgba(245, 158, 11, 0.8)',
          },
        },
      },

      // Transition durations
      transitionDuration: {
        'fast': '150ms',
        'DEFAULT': '250ms',
        'slow': '400ms',
      },
    },
  },
  plugins: [
    require('daisyui'),
  ],
}
