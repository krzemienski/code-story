/**
 * OAuth callback handler page.
 * Handles the redirect from Supabase OAuth providers.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { supabase } from '@/lib/supabase'

export function AuthCallbackPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get the auth code from URL
        const { data, error } = await supabase.auth.getSession()

        if (error) {
          console.error('Auth callback error:', error)
          setError(error.message)
          return
        }

        if (data.session) {
          // Successful login - redirect to dashboard
          navigate('/dashboard', { replace: true })
        } else {
          // No session - redirect to login
          navigate('/login', { replace: true })
        }
      } catch (err) {
        console.error('Callback processing error:', err)
        setError('Failed to process authentication')
      }
    }

    // Small delay to allow URL hash to be processed
    const timer = setTimeout(handleCallback, 100)
    return () => clearTimeout(timer)
  }, [navigate])

  if (error) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2 text-destructive">
            Authentication Error
          </h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <a
            href="/login"
            className="text-primary hover:underline"
          >
            Return to login
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
        <p className="text-muted-foreground">Completing sign in...</p>
      </div>
    </div>
  )
}

export default AuthCallbackPage
