/**
 * Dashboard page showing user's stories and quick actions.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Clock, Headphones, Trash2 } from 'lucide-react'
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Badge,
  Progress,
} from '@/components/ui'
import { useAuth } from '@/contexts/AuthContext'
import { supabase, type Story } from '@/lib/supabase'

export function DashboardPage() {
  const { user, profile } = useAuth()
  const [stories, setStories] = useState<Story[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (user) {
      loadStories()
    }
  }, [user])

  const loadStories = async () => {
    if (!user) return

    try {
      const { data, error } = await supabase
        .from('stories')
        .select('*')
        .eq('user_id', user.id)
        .order('created_at', { ascending: false })

      if (error) throw error
      setStories(data || [])
    } catch (err) {
      console.error('Failed to load stories:', err)
    } finally {
      setLoading(false)
    }
  }

  const deleteStory = async (storyId: number) => {
    if (!confirm('Are you sure you want to delete this story?')) return

    try {
      const { error } = await supabase
        .from('stories')
        .delete()
        .eq('id', storyId)

      if (error) throw error
      setStories(stories.filter(s => s.id !== storyId))
    } catch (err) {
      console.error('Failed to delete story:', err)
    }
  }

  const getStatusBadge = (status: Story['status']) => {
    switch (status) {
      case 'complete':
        return <Badge className="bg-green-500">Complete</Badge>
      case 'generating':
      case 'synthesizing':
        return <Badge className="bg-yellow-500">Processing</Badge>
      case 'analyzing':
        return <Badge className="bg-blue-500">Analyzing</Badge>
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>
      case 'pending':
      default:
        return <Badge variant="secondary">Pending</Badge>
    }
  }

  return (
    <div className="container mx-auto py-8 px-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">
            Welcome{profile?.email ? `, ${profile.email.split('@')[0]}` : ''}
          </h1>
          <p className="text-muted-foreground">
            Create and manage your code stories
          </p>
        </div>
        <Button asChild>
          <Link to="/new-story">
            <Plus className="h-4 w-4 mr-2" />
            New Story
          </Link>
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid md:grid-cols-3 gap-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Stories</CardDescription>
            <CardTitle className="text-3xl">{stories.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed</CardDescription>
            <CardTitle className="text-3xl">
              {stories.filter(s => s.status === 'complete').length}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Usage Quota</CardDescription>
            <CardTitle className="text-3xl">
              {profile?.usage_quota || 0}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Stories List */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Your Stories</h2>

        {loading ? (
          <div className="text-center py-8 text-muted-foreground">
            Loading stories...
          </div>
        ) : stories.length === 0 ? (
          <Card className="py-12">
            <CardContent className="text-center">
              <Headphones className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-medium mb-2">No stories yet</h3>
              <p className="text-muted-foreground mb-4">
                Create your first code story to get started
              </p>
              <Button asChild>
                <Link to="/new-story">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Story
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {stories.map((story) => (
              <Card key={story.id} className="hover:bg-accent/50 transition-colors">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg">
                        <Link
                          to={`/story/${story.id}`}
                          className="hover:underline"
                        >
                          {story.title || 'Untitled Story'}
                        </Link>
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2 mt-1">
                        <Clock className="h-3 w-3" />
                        {new Date(story.created_at).toLocaleDateString()}
                        <span>•</span>
                        <span className="capitalize">{story.narrative_style}</span>
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(story.status)}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteStory(story.id)}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                {(story.status === 'generating' || story.status === 'synthesizing' || story.status === 'analyzing') && (
                  <CardContent className="pt-0">
                    <Progress value={50} className="h-1" />
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DashboardPage
