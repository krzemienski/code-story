/**
 * New Story page - repo input form and intent chat interface.
 * Combines 07-03 (Repo Input) and 07-04 (Intent Chat).
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Github,
  Loader2,
  Send,
  Sparkles,
  ArrowRight,
  MessageCircle,
  Bot,
  User,
} from 'lucide-react'
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Badge,
  ScrollArea,
} from '@/components/ui'
import { useAuth } from '@/contexts/AuthContext'
import { supabase, type NarrativeStyle } from '@/lib/supabase'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export function NewStoryPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Form state
  const [repoUrl, setRepoUrl] = useState('')
  const [repoError, setRepoError] = useState('')
  const [validatingRepo, setValidatingRepo] = useState(false)
  const [repoValid, setRepoValid] = useState(false)
  const [repoInfo, setRepoInfo] = useState<{ owner: string; name: string } | null>(null)

  // Chat state
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Hi! I'm your Code Story assistant. Tell me about what you'd like to learn from this codebase. What aspects interest you most?",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // Story config - using actual enum values
  const [style, setStyle] = useState<NarrativeStyle>('storytelling')
  const [generating, setGenerating] = useState(false)

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const validateRepoUrl = async () => {
    setRepoError('')
    setRepoValid(false)
    setValidatingRepo(true)

    try {
      // Basic URL validation
      const urlPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/
      if (!urlPattern.test(repoUrl)) {
        setRepoError('Please enter a valid GitHub repository URL')
        return
      }

      // Extract owner/repo
      const match = repoUrl.match(/github\.com\/([\w-]+)\/([\w.-]+)/)
      if (!match) {
        setRepoError('Could not parse repository URL')
        return
      }

      const [, owner, name] = match

      // Check if repo exists via GitHub API
      const response = await fetch(`https://api.github.com/repos/${owner}/${name}`)
      if (!response.ok) {
        if (response.status === 404) {
          setRepoError('Repository not found or is private')
        } else {
          setRepoError('Failed to validate repository')
        }
        return
      }

      setRepoInfo({ owner, name })
      setRepoValid(true)
    } catch (err) {
      setRepoError('Failed to validate repository')
    } finally {
      setValidatingRepo(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || chatLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setChatLoading(true)

    try {
      // Call backend API for intent analysis
      const session = await supabase.auth.getSession()
      const response = await fetch(`${import.meta.env.VITE_API_URL}/stories/analyze-intent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.data.session?.access_token}`,
        },
        body: JSON.stringify({
          message: input,
          repo_url: repoUrl,
          conversation: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      let assistantContent = "I understand you're interested in learning more about this codebase. Let me help you create a personalized story. What narrative style would you prefer? I can create a storytelling narrative, technical deep-dive, educational walkthrough, casual overview, or executive summary."

      if (response.ok) {
        const data = await response.json()
        assistantContent = data.response || assistantContent
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      console.error('Chat error:', err)
      // Provide fallback response
      const fallbackMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "Thanks for sharing that! Based on your interests, I'll create a compelling narrative. When you're ready, select your preferred style and click 'Generate Story'.",
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, fallbackMessage])
    } finally {
      setChatLoading(false)
    }
  }

  const generateStory = async () => {
    if (!user || !repoValid || !repoInfo) return

    setGenerating(true)

    try {
      // First, create or get repository record
      const { data: existingRepo } = await supabase
        .from('repositories')
        .select('id')
        .eq('owner', repoInfo.owner)
        .eq('name', repoInfo.name)
        .single()

      let repositoryId: number

      if (existingRepo) {
        repositoryId = existingRepo.id
      } else {
        // Create new repository record
        const { data: newRepo, error: repoError } = await supabase
          .from('repositories')
          .insert({
            owner: repoInfo.owner,
            name: repoInfo.name,
            url: repoUrl,
          })
          .select('id')
          .single()

        if (repoError) throw repoError
        repositoryId = newRepo.id
      }

      // Create story in database
      const { data: story, error } = await supabase
        .from('stories')
        .insert({
          user_id: user.id,
          repository_id: repositoryId,
          title: `Story: ${repoInfo.owner}/${repoInfo.name}`,
          narrative_style: style,
          status: 'pending',
        })
        .select()
        .single()

      if (error) throw error

      // Trigger story generation via API
      const session = await supabase.auth.getSession()
      await fetch(`${import.meta.env.VITE_API_URL}/stories/${story.id}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.data.session?.access_token}`,
        },
        body: JSON.stringify({
          conversation: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      // Navigate to story page
      navigate(`/story/${story.id}`)
    } catch (err) {
      console.error('Failed to generate story:', err)
      alert('Failed to create story. Please try again.')
    } finally {
      setGenerating(false)
    }
  }

  const styleDescriptions: Record<NarrativeStyle, string> = {
    storytelling: 'Engaging narrative with characters and plot',
    technical: 'Deep-dive with code examples and details',
    educational: 'Step-by-step learning experience',
    casual: 'Light and easy-to-follow overview',
    executive: 'High-level summary for decision makers',
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Create New Story</h1>
        <p className="text-muted-foreground">
          Transform any GitHub repository into an engaging audio narrative
        </p>
      </div>

      <div className="space-y-6">
        {/* Step 1: Repository Input */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant="outline">1</Badge>
              <Github className="h-5 w-5" />
              Connect Repository
            </CardTitle>
            <CardDescription>
              Enter a public GitHub repository URL
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  placeholder="https://github.com/owner/repo"
                  value={repoUrl}
                  onChange={(e) => {
                    setRepoUrl(e.target.value)
                    setRepoValid(false)
                    setRepoError('')
                  }}
                  className={repoError ? 'border-destructive' : repoValid ? 'border-green-500' : ''}
                />
                {repoError && (
                  <p className="text-sm text-destructive mt-1">{repoError}</p>
                )}
              </div>
              <Button
                onClick={validateRepoUrl}
                disabled={!repoUrl || validatingRepo}
              >
                {validatingRepo ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Validate'
                )}
              </Button>
            </div>
            {repoValid && repoInfo && (
              <p className="text-sm text-green-600 flex items-center gap-1">
                <Sparkles className="h-4 w-4" />
                Repository validated: {repoInfo.owner}/{repoInfo.name}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Step 2: Intent Chat */}
        <Card className={!repoValid ? 'opacity-50 pointer-events-none' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant="outline">2</Badge>
              <MessageCircle className="h-5 w-5" />
              Tell Me Your Interests
            </CardTitle>
            <CardDescription>
              Chat with our AI to customize your story
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-64 border rounded-lg p-4 mb-4">
              <div className="space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex gap-3 ${
                      message.role === 'user' ? 'flex-row-reverse' : ''
                    }`}
                  >
                    <div
                      className={`h-8 w-8 rounded-full flex items-center justify-center ${
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      {message.role === 'user' ? (
                        <User className="h-4 w-4" />
                      ) : (
                        <Bot className="h-4 w-4" />
                      )}
                    </div>
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      <p className="text-sm">{message.content}</p>
                    </div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="flex gap-3">
                    <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                      <Bot className="h-4 w-4" />
                    </div>
                    <div className="bg-muted rounded-lg p-3">
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>
            <div className="flex gap-2">
              <Input
                placeholder="Tell me what you want to learn..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                disabled={chatLoading}
              />
              <Button onClick={sendMessage} disabled={!input.trim() || chatLoading}>
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Step 3: Style Selection */}
        <Card className={!repoValid ? 'opacity-50 pointer-events-none' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant="outline">3</Badge>
              <Sparkles className="h-5 w-5" />
              Choose Narrative Style
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {(Object.keys(styleDescriptions) as NarrativeStyle[]).map((s) => (
                <Button
                  key={s}
                  variant={style === s ? 'default' : 'outline'}
                  className="h-auto py-3 flex flex-col"
                  onClick={() => setStyle(s)}
                >
                  <span className="capitalize font-medium">{s}</span>
                  <span className="text-xs opacity-80 mt-1">
                    {styleDescriptions[s].split(' ').slice(0, 3).join(' ')}...
                  </span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Generate Button */}
        <Button
          size="lg"
          className="w-full"
          onClick={generateStory}
          disabled={!repoValid || generating}
        >
          {generating ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Creating Your Story...
            </>
          ) : (
            <>
              <ArrowRight className="h-4 w-4 mr-2" />
              Generate Story
            </>
          )}
        </Button>
      </div>
    </div>
  )
}

export default NewStoryPage
