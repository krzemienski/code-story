/**
 * Code Story - Shared Theme Configuration
 *
 * This file defines theme tokens that can be shared between:
 * - React Web (via CSS variables in index.css)
 * - React Native/Expo (via NativeWind configuration)
 *
 * Design Philosophy: Dark, Flat, Elegant
 * - Dark: Deep slate backgrounds (oklch 0.12-0.18 lightness)
 * - Flat: Minimal shadows, clean edges
 * - Elegant: Refined cyan accent, sophisticated typography
 */

// OKLCH color values for cross-platform consistency
export const colors = {
  // Backgrounds
  background: { l: 0.12, c: 0.02, h: 250 },
  card: { l: 0.14, c: 0.02, h: 250 },
  popover: { l: 0.14, c: 0.02, h: 250 },

  // Foregrounds
  foreground: { l: 0.98, c: 0.01, h: 250 },
  cardForeground: { l: 0.98, c: 0.01, h: 250 },
  popoverForeground: { l: 0.98, c: 0.01, h: 250 },

  // Primary (Cyan accent)
  primary: { l: 0.7, c: 0.15, h: 200 },
  primaryForeground: { l: 0.12, c: 0.02, h: 250 },

  // Secondary
  secondary: { l: 0.18, c: 0.02, h: 250 },
  secondaryForeground: { l: 0.98, c: 0.01, h: 250 },

  // Muted
  muted: { l: 0.16, c: 0.02, h: 250 },
  mutedForeground: { l: 0.6, c: 0.02, h: 250 },

  // Accent
  accent: { l: 0.18, c: 0.02, h: 250 },
  accentForeground: { l: 0.98, c: 0.01, h: 250 },

  // Destructive
  destructive: { l: 0.5, c: 0.15, h: 25 },
  destructiveForeground: { l: 0.98, c: 0.01, h: 250 },

  // UI Elements
  border: { l: 0.2, c: 0.02, h: 250 },
  input: { l: 0.2, c: 0.02, h: 250 },
  ring: { l: 0.7, c: 0.15, h: 200 },
} as const

// Radius tokens
export const radius = {
  sm: '0.25rem',
  md: '0.5rem',
  lg: '0.75rem',
  xl: '1rem',
} as const

// Convert OKLCH to CSS string
export function oklch(color: { l: number; c: number; h: number }): string {
  return `oklch(${color.l} ${color.c} ${color.h})`
}

// Generate CSS variables object for inline styles or JS usage
export function getCssVariables() {
  return {
    '--color-background': oklch(colors.background),
    '--color-foreground': oklch(colors.foreground),
    '--color-card': oklch(colors.card),
    '--color-card-foreground': oklch(colors.cardForeground),
    '--color-popover': oklch(colors.popover),
    '--color-popover-foreground': oklch(colors.popoverForeground),
    '--color-primary': oklch(colors.primary),
    '--color-primary-foreground': oklch(colors.primaryForeground),
    '--color-secondary': oklch(colors.secondary),
    '--color-secondary-foreground': oklch(colors.secondaryForeground),
    '--color-muted': oklch(colors.muted),
    '--color-muted-foreground': oklch(colors.mutedForeground),
    '--color-accent': oklch(colors.accent),
    '--color-accent-foreground': oklch(colors.accentForeground),
    '--color-destructive': oklch(colors.destructive),
    '--color-destructive-foreground': oklch(colors.destructiveForeground),
    '--color-border': oklch(colors.border),
    '--color-input': oklch(colors.input),
    '--color-ring': oklch(colors.ring),
  }
}

// NativeWind-compatible color palette (hex approximations for RN)
// These are sRGB approximations of the OKLCH colors
export const nativeWindColors = {
  background: '#1a1a2e',
  foreground: '#fafafa',
  card: '#1e1e38',
  cardForeground: '#fafafa',
  popover: '#1e1e38',
  popoverForeground: '#fafafa',
  primary: '#22d3ee',
  primaryForeground: '#1a1a2e',
  secondary: '#2a2a44',
  secondaryForeground: '#fafafa',
  muted: '#242438',
  mutedForeground: '#9898a8',
  accent: '#2a2a44',
  accentForeground: '#fafafa',
  destructive: '#ef4444',
  destructiveForeground: '#fafafa',
  border: '#2e2e48',
  input: '#2e2e48',
  ring: '#22d3ee',
} as const

// Spacing scale (shared)
export const spacing = {
  0: '0',
  1: '0.25rem',
  2: '0.5rem',
  3: '0.75rem',
  4: '1rem',
  5: '1.25rem',
  6: '1.5rem',
  8: '2rem',
  10: '2.5rem',
  12: '3rem',
  16: '4rem',
  20: '5rem',
  24: '6rem',
} as const
