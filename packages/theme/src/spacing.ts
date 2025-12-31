/**
 * Code Story - Spacing & Layout Tokens
 *
 * Consistent spacing scale for both web and native.
 * Based on 4px base unit for pixel-perfect alignment.
 */

// Spacing scale (in rem for web, converted to pixels for native)
export const spacing = {
  0: 0,
  0.5: 2,
  1: 4,
  1.5: 6,
  2: 8,
  2.5: 10,
  3: 12,
  3.5: 14,
  4: 16,
  5: 20,
  6: 24,
  7: 28,
  8: 32,
  9: 36,
  10: 40,
  11: 44,
  12: 48,
  14: 56,
  16: 64,
  20: 80,
  24: 96,
  28: 112,
  32: 128,
  36: 144,
  40: 160,
  44: 176,
  48: 192,
  52: 208,
  56: 224,
  60: 240,
  64: 256,
  72: 288,
  80: 320,
  96: 384,
} as const

// Spacing in rem for web
export const spacingRem = Object.fromEntries(
  Object.entries(spacing).map(([key, value]) => [key, `${value / 16}rem`])
) as Record<keyof typeof spacing, string>

// Border radius tokens
export const radius = {
  none: 0,
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  '2xl': 24,
  '3xl': 32,
  full: 9999,
} as const

// Border radius in rem for web
export const radiusRem = {
  none: '0',
  sm: '0.25rem',
  md: '0.5rem',
  lg: '0.75rem',
  xl: '1rem',
  '2xl': '1.5rem',
  '3xl': '2rem',
  full: '9999px',
} as const

// Z-index scale
export const zIndex = {
  0: 0,
  10: 10,
  20: 20,
  30: 30,
  40: 40,
  50: 50,
  auto: 'auto',
} as const

// Container max-widths
export const containers = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const

// Breakpoints (for responsive design)
export const breakpoints = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const

export type SpacingKey = keyof typeof spacing
export type RadiusKey = keyof typeof radius
export type BreakpointKey = keyof typeof breakpoints
