/**
 * Code Story - Tailwind CSS v4 Configuration
 *
 * Exports CSS custom properties for use with @theme directive.
 * Compatible with Tailwind CSS v4's new configuration system.
 */

import { oklchColors, oklchToCss, hexColors } from './colors'
import { radiusRem } from './spacing'
import { fontFamily, fontSizeRem, letterSpacingEm } from './typography'

// CSS variables for @theme directive
export function getCssThemeVariables(): Record<string, string> {
  return {
    // Colors
    '--color-background': oklchToCss(oklchColors.background),
    '--color-foreground': oklchToCss(oklchColors.foreground),
    '--color-card': oklchToCss(oklchColors.card),
    '--color-card-foreground': oklchToCss(oklchColors.cardForeground),
    '--color-popover': oklchToCss(oklchColors.popover),
    '--color-popover-foreground': oklchToCss(oklchColors.popoverForeground),
    '--color-primary': oklchToCss(oklchColors.primary),
    '--color-primary-foreground': oklchToCss(oklchColors.primaryForeground),
    '--color-secondary': oklchToCss(oklchColors.secondary),
    '--color-secondary-foreground': oklchToCss(oklchColors.secondaryForeground),
    '--color-muted': oklchToCss(oklchColors.muted),
    '--color-muted-foreground': oklchToCss(oklchColors.mutedForeground),
    '--color-accent': oklchToCss(oklchColors.accent),
    '--color-accent-foreground': oklchToCss(oklchColors.accentForeground),
    '--color-destructive': oklchToCss(oklchColors.destructive),
    '--color-destructive-foreground': oklchToCss(oklchColors.destructiveForeground),
    '--color-border': oklchToCss(oklchColors.border),
    '--color-input': oklchToCss(oklchColors.input),
    '--color-ring': oklchToCss(oklchColors.ring),
    '--color-chart-1': oklchToCss(oklchColors.chart1),
    '--color-chart-2': oklchToCss(oklchColors.chart2),
    '--color-chart-3': oklchToCss(oklchColors.chart3),
    '--color-chart-4': oklchToCss(oklchColors.chart4),
    '--color-chart-5': oklchToCss(oklchColors.chart5),

    // Radius
    '--radius-sm': radiusRem.sm,
    '--radius-md': radiusRem.md,
    '--radius-lg': radiusRem.lg,
    '--radius-xl': radiusRem.xl,
  }
}

// Generate @theme CSS block content
export function generateThemeCss(): string {
  const vars = getCssThemeVariables()
  const lines = Object.entries(vars).map(([key, value]) => `  ${key}: ${value};`)
  return `@theme {\n${lines.join('\n')}\n}`
}

// Tailwind v4 theme extension object (for advanced customization)
export const tailwindTheme = {
  colors: {
    background: 'var(--color-background)',
    foreground: 'var(--color-foreground)',
    card: {
      DEFAULT: 'var(--color-card)',
      foreground: 'var(--color-card-foreground)',
    },
    popover: {
      DEFAULT: 'var(--color-popover)',
      foreground: 'var(--color-popover-foreground)',
    },
    primary: {
      DEFAULT: 'var(--color-primary)',
      foreground: 'var(--color-primary-foreground)',
    },
    secondary: {
      DEFAULT: 'var(--color-secondary)',
      foreground: 'var(--color-secondary-foreground)',
    },
    muted: {
      DEFAULT: 'var(--color-muted)',
      foreground: 'var(--color-muted-foreground)',
    },
    accent: {
      DEFAULT: 'var(--color-accent)',
      foreground: 'var(--color-accent-foreground)',
    },
    destructive: {
      DEFAULT: 'var(--color-destructive)',
      foreground: 'var(--color-destructive-foreground)',
    },
    border: 'var(--color-border)',
    input: 'var(--color-input)',
    ring: 'var(--color-ring)',
    chart: {
      1: 'var(--color-chart-1)',
      2: 'var(--color-chart-2)',
      3: 'var(--color-chart-3)',
      4: 'var(--color-chart-4)',
      5: 'var(--color-chart-5)',
    },
  },
  borderRadius: {
    sm: 'var(--radius-sm)',
    md: 'var(--radius-md)',
    lg: 'var(--radius-lg)',
    xl: 'var(--radius-xl)',
  },
  fontFamily: {
    sans: fontFamily.sans.join(', '),
    mono: fontFamily.mono.join(', '),
  },
}

// Hex colors for fallback or non-OKLCH browsers
export { hexColors as tailwindHexColors }
