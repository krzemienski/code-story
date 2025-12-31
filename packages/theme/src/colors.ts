/**
 * Code Story - Color Palette
 *
 * Design Philosophy: Dark, Flat, Elegant
 * - Dark: Deep slate backgrounds (oklch 0.12-0.18 lightness)
 * - Flat: Minimal shadows, clean edges
 * - Elegant: Refined cyan accent, sophisticated typography
 *
 * All colors defined in OKLCH for perceptual uniformity.
 * Converted to hex for React Native compatibility.
 */

// OKLCH color type
export interface OklchColor {
  l: number // Lightness (0-1)
  c: number // Chroma (0-0.4)
  h: number // Hue (0-360)
}

// Semantic color tokens
export const oklchColors = {
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

  // Chart colors
  chart1: { l: 0.7, c: 0.15, h: 200 },
  chart2: { l: 0.65, c: 0.12, h: 160 },
  chart3: { l: 0.6, c: 0.13, h: 280 },
  chart4: { l: 0.55, c: 0.14, h: 40 },
  chart5: { l: 0.7, c: 0.11, h: 320 },
} as const

// Hex color palette (sRGB approximations of OKLCH colors)
// These are calculated conversions for React Native compatibility
export const hexColors = {
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
  chart1: '#22d3ee',
  chart2: '#34d399',
  chart3: '#a78bfa',
  chart4: '#fbbf24',
  chart5: '#f472b6',
} as const

// RGB values for animations and interpolation
export const rgbColors = {
  background: [26, 26, 46],
  foreground: [250, 250, 250],
  card: [30, 30, 56],
  cardForeground: [250, 250, 250],
  popover: [30, 30, 56],
  popoverForeground: [250, 250, 250],
  primary: [34, 211, 238],
  primaryForeground: [26, 26, 46],
  secondary: [42, 42, 68],
  secondaryForeground: [250, 250, 250],
  muted: [36, 36, 56],
  mutedForeground: [152, 152, 168],
  accent: [42, 42, 68],
  accentForeground: [250, 250, 250],
  destructive: [239, 68, 68],
  destructiveForeground: [250, 250, 250],
  border: [46, 46, 72],
  input: [46, 46, 72],
  ring: [34, 211, 238],
} as const

// Color utility functions
export function oklchToCss(color: OklchColor): string {
  return `oklch(${color.l} ${color.c} ${color.h})`
}

export function rgbToHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map((x) => x.toString(16).padStart(2, '0')).join('')
}

export function rgbToCss(rgb: number[]): string {
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`
}

export function withOpacity(hex: string, opacity: number): string {
  const alpha = Math.round(opacity * 255)
    .toString(16)
    .padStart(2, '0')
  return hex + alpha
}

export type ColorKey = keyof typeof hexColors
export type OklchColorKey = keyof typeof oklchColors
