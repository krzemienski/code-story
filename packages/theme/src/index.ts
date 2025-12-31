/**
 * Code Story - Shared Theme Package
 *
 * Cross-platform theme for React (web) and React Native (Expo/NativeWind).
 *
 * Usage:
 *
 * Web (Tailwind v4):
 * ```ts
 * import { generateThemeCss, tailwindTheme } from '@codestory/theme/tailwind'
 * ```
 *
 * React Native (NativeWind):
 * ```ts
 * import { nativeWindPreset, nativeTheme } from '@codestory/theme/nativewind'
 * ```
 *
 * Core tokens (platform-agnostic):
 * ```ts
 * import { hexColors, spacing, fontSize } from '@codestory/theme'
 * ```
 */

// Core exports
export * from './colors'
export * from './spacing'
export * from './typography'

// Platform-specific (re-exported for convenience)
export { getCssThemeVariables, generateThemeCss, tailwindTheme } from './tailwind'
export { nativeWindPreset, nativeTheme, nativeStyles } from './nativewind'
