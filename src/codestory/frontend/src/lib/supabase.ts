/**
 * Supabase client configuration for the frontend.
 *
 * This module provides the Supabase client instance and auth helpers
 * for use throughout the React application.
 */

import { createClient, type SupabaseClient, type User, type Session } from '@supabase/supabase-js'
import type { Database } from './supabase-types'

// Environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    'Missing Supabase environment variables. Auth functionality will not work. ' +
    'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env file.'
  )
}

/**
 * The Supabase client instance with typed database schema.
 * Use this throughout your application for database and auth operations.
 */
export const supabase: SupabaseClient<Database> = createClient<Database>(
  supabaseUrl || '',
  supabaseAnonKey || '',
  {
    auth: {
      // Persist auth state in localStorage
      persistSession: true,
      // Auto refresh tokens before expiry
      autoRefreshToken: true,
      // Detect session from URL (for OAuth redirects)
      detectSessionInUrl: true,
      // Storage key for the session
      storageKey: 'codestory-auth',
    },
  }
)

// =============================================================================
// Auth Helpers
// =============================================================================

/**
 * Get the current user synchronously from the cached session.
 * Returns null if not logged in.
 * Note: Use getUser() or getSession() for async operations.
 */
export function getCurrentUser(): User | null {
  // This is a placeholder for synchronous access.
  // The actual user should be retrieved via getUser() async call.
  return null
}

/**
 * Get the current session.
 */
export async function getSession(): Promise<Session | null> {
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    console.error('Error getting session:', error.message)
    return null
  }
  return data.session
}

/**
 * Get the current user.
 */
export async function getUser(): Promise<User | null> {
  const { data, error } = await supabase.auth.getUser()
  if (error) {
    console.error('Error getting user:', error.message)
    return null
  }
  return data.user
}

/**
 * Sign in with email and password.
 */
export async function signInWithPassword(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) {
    throw new Error(error.message)
  }

  return data
}

/**
 * Sign up with email and password.
 */
export async function signUp(email: string, password: string, name?: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        name: name || '',
      },
    },
  })

  if (error) {
    throw new Error(error.message)
  }

  return data
}

/**
 * Sign in with OAuth provider.
 */
export async function signInWithOAuth(provider: 'github' | 'google' | 'apple' | 'discord') {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })

  if (error) {
    throw new Error(error.message)
  }

  return data
}

/**
 * Sign out the current user.
 */
export async function signOut() {
  const { error } = await supabase.auth.signOut()
  if (error) {
    throw new Error(error.message)
  }
}

/**
 * Send password reset email.
 */
export async function resetPassword(email: string) {
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/auth/reset-password`,
  })

  if (error) {
    throw new Error(error.message)
  }
}

/**
 * Update user password.
 */
export async function updatePassword(newPassword: string) {
  const { error } = await supabase.auth.updateUser({
    password: newPassword,
  })

  if (error) {
    throw new Error(error.message)
  }
}

/**
 * Subscribe to auth state changes.
 * Returns an unsubscribe function.
 */
export function onAuthStateChange(
  callback: (event: string, session: Session | null) => void
) {
  const { data } = supabase.auth.onAuthStateChange((event, session) => {
    callback(event, session)
  })

  return data.subscription.unsubscribe
}

// =============================================================================
// Database Helpers (typed)
// =============================================================================

/**
 * Get the current user's profile from the profiles table.
 */
export async function getProfile(userId: string) {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', userId)
    .single()

  if (error && error.code !== 'PGRST116') {
    // PGRST116 = no rows returned
    throw new Error(error.message)
  }

  return data
}

/**
 * Update the current user's profile.
 */
export async function updateProfile(
  userId: string,
  updates: Partial<Database['public']['Tables']['profiles']['Update']>
) {
  const { data, error } = await supabase
    .from('profiles')
    .update(updates)
    .eq('id', userId)
    .select()
    .single()

  if (error) {
    throw new Error(error.message)
  }

  return data
}

// =============================================================================
// Type exports
// =============================================================================

export type { User, Session }
export type { Database }
export type Profile = Database['public']['Tables']['profiles']['Row']
export type Story = Database['public']['Tables']['stories']['Row']
export type StoryChapter = Database['public']['Tables']['story_chapters']['Row']
export type Repository = Database['public']['Tables']['repositories']['Row']
export type StoryIntent = Database['public']['Tables']['story_intents']['Row']
export type NarrativeStyle = Database['public']['Enums']['narrative_style']
export type StoryStatus = Database['public']['Enums']['story_status']
