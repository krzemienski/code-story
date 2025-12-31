/**
 * Code Story - NativeWind Configuration
 *
 * Theme configuration for React Native with NativeWind.
 * Uses hex colors since React Native doesn't support OKLCH.
 */

import { hexColors, rgbColors, withOpacity } from './colors'
import { spacing, radius } from './spacing'
import { fontSize, fontWeight, lineHeight } from './typography'

// NativeWind theme preset
export const nativeWindPreset = {
  theme: {
    extend: {
      colors: {
        background: hexColors.background,
        foreground: hexColors.foreground,
        card: {
          DEFAULT: hexColors.card,
          foreground: hexColors.cardForeground,
        },
        popover: {
          DEFAULT: hexColors.popover,
          foreground: hexColors.popoverForeground,
        },
        primary: {
          DEFAULT: hexColors.primary,
          foreground: hexColors.primaryForeground,
        },
        secondary: {
          DEFAULT: hexColors.secondary,
          foreground: hexColors.secondaryForeground,
        },
        muted: {
          DEFAULT: hexColors.muted,
          foreground: hexColors.mutedForeground,
        },
        accent: {
          DEFAULT: hexColors.accent,
          foreground: hexColors.accentForeground,
        },
        destructive: {
          DEFAULT: hexColors.destructive,
          foreground: hexColors.destructiveForeground,
        },
        border: hexColors.border,
        input: hexColors.input,
        ring: hexColors.ring,
        chart: {
          1: hexColors.chart1,
          2: hexColors.chart2,
          3: hexColors.chart3,
          4: hexColors.chart4,
          5: hexColors.chart5,
        },
      },
      borderRadius: {
        sm: radius.sm,
        md: radius.md,
        lg: radius.lg,
        xl: radius.xl,
      },
    },
  },
}

// React Native StyleSheet-compatible theme object
export const nativeTheme = {
  colors: hexColors,
  spacing,
  radius,
  fontSize,
  fontWeight,
  lineHeight,
}

// Utility for creating opacity variants in React Native
export function colorWithOpacity(
  colorKey: keyof typeof hexColors,
  opacity: number
): string {
  return withOpacity(hexColors[colorKey], opacity)
}

// Common style presets for React Native
export const nativeStyles = {
  container: {
    flex: 1,
    backgroundColor: hexColors.background,
  },
  card: {
    backgroundColor: hexColors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: hexColors.border,
    padding: spacing[4],
  },
  text: {
    color: hexColors.foreground,
    fontSize: fontSize.base,
  },
  textMuted: {
    color: hexColors.mutedForeground,
    fontSize: fontSize.sm,
  },
  heading: {
    color: hexColors.foreground,
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.bold,
  },
  button: {
    backgroundColor: hexColors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing[2],
    paddingHorizontal: spacing[4],
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
  },
  buttonText: {
    color: hexColors.primaryForeground,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
  },
  input: {
    backgroundColor: hexColors.input,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: hexColors.border,
    paddingVertical: spacing[2],
    paddingHorizontal: spacing[3],
    color: hexColors.foreground,
    fontSize: fontSize.sm,
  },
}

// Export individual values for convenience
export { hexColors as colors, spacing, radius, fontSize, fontWeight, lineHeight }
