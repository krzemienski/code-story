/**
 * Story detail page with chapters and audio player.
 * Implements 07-05 (Dashboard detail) and 07-06 (Audio Player).
 */

import { useEffect, useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Download,
  Share2,
  Clock,
  Loader2,
} from 'lucide-react'
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Badge,
  Progress,
  Slider,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  ScrollArea,
} from '@/components/ui'
import { supabase, type Story, type StoryChapter } from '@/lib/supabase'

export function StoryDetailPage() {
  const { id } = useParams<{ id: string }>()
  const audioRef = useRef<HTMLAudioElement>(null)

  // Story data
  const [story, setStory] = useState<Story | null>(null)
  const [chapters, setChapters] = useState<StoryChapter[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Audio player state
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [currentChapter, setCurrentChapter] = useState(0)

  // SSE progress tracking
  const [generationProgress, setGenerationProgress] = useState(0)

  useEffect(() => {
    if (id) {
      loadStory()
      loadChapters()
    }
  }, [id])

  // SSE connection for real-time updates
  useEffect(() => {
    if (!story || (story.status !== 'generating' && story.status !== 'analyzing' && story.status !== 'synthesizing')) return

    const eventSource = new EventSource(
      `${import.meta.env.VITE_API_URL}/stories/${id}/progress`
    )

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.progress) {
        setGenerationProgress(data.progress)
      }
      if (data.status === 'complete') {
        loadStory()
        loadChapters()
        eventSource.close()
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
    }

    return () => eventSource.close()
  }, [story?.status, id])

  const loadStory = async () => {
    if (!id) return

    try {
      const { data, error } = await supabase
        .from('stories')
        .select('*')
        .eq('id', parseInt(id, 10))
        .single()

      if (error) throw error
      setStory(data)
    } catch (err) {
      console.error('Failed to load story:', err)
      setError('Story not found')
    } finally {
      setLoading(false)
    }
  }

  const loadChapters = async () => {
    if (!id) return

    try {
      const { data, error } = await supabase
        .from('story_chapters')
        .select('*')
        .eq('story_id', parseInt(id, 10))
        .order('order', { ascending: true })

      if (error) throw error
      setChapters(data || [])
    } catch (err) {
      console.error('Failed to load chapters:', err)
    }
  }

  // Audio controls
  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause()
      } else {
        audioRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime)
    }
  }

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration)
    }
  }

  const handleSeek = (value: number[]) => {
    if (audioRef.current) {
      audioRef.current.currentTime = value[0]
      setCurrentTime(value[0])
    }
  }

  const handleVolumeChange = (value: number[]) => {
    const newVolume = value[0]
    setVolume(newVolume)
    if (audioRef.current) {
      audioRef.current.volume = newVolume
    }
    setIsMuted(newVolume === 0)
  }

  const toggleMute = () => {
    if (audioRef.current) {
      if (isMuted) {
        audioRef.current.volume = volume || 1
        setIsMuted(false)
      } else {
        audioRef.current.volume = 0
        setIsMuted(true)
      }
    }
  }

  const playChapter = (index: number) => {
    setCurrentChapter(index)
    if (audioRef.current && chapters[index]?.audio_url) {
      audioRef.current.src = chapters[index].audio_url!
      audioRef.current.play()
      setIsPlaying(true)
    }
  }

  const skipPrevious = () => {
    if (currentChapter > 0) {
      playChapter(currentChapter - 1)
    }
  }

  const skipNext = () => {
    if (currentChapter < chapters.length - 1) {
      playChapter(currentChapter + 1)
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
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

  if (loading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (error || !story) {
    return (
      <div className="container mx-auto py-8 px-4 text-center">
        <h2 className="text-xl font-semibold mb-2">Story Not Found</h2>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button asChild>
          <Link to="/dashboard">Back to Dashboard</Link>
        </Button>
      </div>
    )
  }

  const isProcessing = story.status === 'generating' || story.status === 'synthesizing' || story.status === 'analyzing'

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      {/* Back Button */}
      <Button variant="ghost" asChild className="mb-4">
        <Link to="/dashboard">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Link>
      </Button>

      {/* Story Header */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-2xl">{story.title}</CardTitle>
              <CardDescription className="flex items-center gap-2 mt-2">
                <Clock className="h-4 w-4" />
                {new Date(story.created_at).toLocaleDateString()}
                <span>•</span>
                <span className="capitalize">{story.narrative_style}</span>
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {getStatusBadge(story.status)}
            </div>
          </div>
        </CardHeader>

        {/* Generation Progress */}
        {isProcessing && (
          <CardContent className="pt-0">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Generating your story...</span>
                <span>{generationProgress}%</span>
              </div>
              <Progress value={generationProgress} />
            </div>
          </CardContent>
        )}
      </Card>

      {/* Audio Player */}
      {story.status === 'complete' && chapters.length > 0 && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <audio
              ref={audioRef}
              src={chapters[currentChapter]?.audio_url || ''}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={skipNext}
            />

            {/* Now Playing */}
            <div className="text-center mb-4">
              <p className="text-sm text-muted-foreground">Now Playing</p>
              <p className="font-medium">{chapters[currentChapter]?.title || `Chapter ${currentChapter + 1}`}</p>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2 mb-4">
              <Slider
                value={[currentTime]}
                max={duration || 100}
                step={1}
                onValueChange={handleSeek}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-4 mb-4">
              <Button variant="ghost" size="icon" onClick={skipPrevious}>
                <SkipBack className="h-5 w-5" />
              </Button>
              <Button
                size="icon"
                className="h-12 w-12 rounded-full"
                onClick={togglePlay}
              >
                {isPlaying ? (
                  <Pause className="h-6 w-6" />
                ) : (
                  <Play className="h-6 w-6 ml-1" />
                )}
              </Button>
              <Button variant="ghost" size="icon" onClick={skipNext}>
                <SkipForward className="h-5 w-5" />
              </Button>
            </div>

            {/* Volume */}
            <div className="flex items-center justify-center gap-2">
              <Button variant="ghost" size="icon" onClick={toggleMute}>
                {isMuted ? (
                  <VolumeX className="h-4 w-4" />
                ) : (
                  <Volume2 className="h-4 w-4" />
                )}
              </Button>
              <Slider
                value={[isMuted ? 0 : volume]}
                max={1}
                step={0.1}
                onValueChange={handleVolumeChange}
                className="w-24"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Chapters List */}
      <Tabs defaultValue="chapters">
        <TabsList className="w-full">
          <TabsTrigger value="chapters" className="flex-1">Chapters</TabsTrigger>
          <TabsTrigger value="transcript" className="flex-1">Transcript</TabsTrigger>
        </TabsList>

        <TabsContent value="chapters" className="mt-4">
          <ScrollArea className="h-[400px]">
            <div className="space-y-2">
              {chapters.length === 0 ? (
                <Card className="py-8">
                  <CardContent className="text-center text-muted-foreground">
                    {isProcessing
                      ? 'Chapters will appear here as they are generated...'
                      : 'No chapters available'}
                  </CardContent>
                </Card>
              ) : (
                chapters.map((chapter, index) => (
                  <Card
                    key={chapter.id}
                    className={`cursor-pointer hover:bg-accent/50 transition-colors ${
                      currentChapter === index ? 'border-primary' : ''
                    }`}
                    onClick={() => playChapter(index)}
                  >
                    <CardHeader className="py-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div
                            className={`h-8 w-8 rounded-full flex items-center justify-center ${
                              currentChapter === index
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-muted'
                            }`}
                          >
                            {currentChapter === index && isPlaying ? (
                              <Pause className="h-4 w-4" />
                            ) : (
                              <Play className="h-4 w-4 ml-0.5" />
                            )}
                          </div>
                          <div>
                            <CardTitle className="text-sm">
                              {chapter.title || `Chapter ${chapter.order}`}
                            </CardTitle>
                            <CardDescription className="text-xs">
                              {chapter.duration_seconds
                                ? formatTime(chapter.duration_seconds)
                                : 'Duration N/A'}
                            </CardDescription>
                          </div>
                        </div>
                        {chapter.audio_url && (
                          <Button variant="ghost" size="icon" asChild>
                            <a href={chapter.audio_url} download>
                              <Download className="h-4 w-4" />
                            </a>
                          </Button>
                        )}
                      </div>
                    </CardHeader>
                  </Card>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="transcript" className="mt-4">
          <ScrollArea className="h-[400px]">
            <Card>
              <CardContent className="pt-4 space-y-6">
                {chapters.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    {isProcessing
                      ? 'Transcript will appear here when generation completes...'
                      : 'No transcript available'}
                  </p>
                ) : (
                  chapters.map((chapter) => (
                    <div key={chapter.id}>
                      <h3 className="font-semibold mb-2">
                        {chapter.title || `Chapter ${chapter.order}`}
                      </h3>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {chapter.script || 'No transcript available'}
                      </p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </ScrollArea>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="flex gap-2 mt-6">
        <Button variant="outline" className="flex-1">
          <Share2 className="h-4 w-4 mr-2" />
          Share
        </Button>
        <Button variant="outline" className="flex-1">
          <Download className="h-4 w-4 mr-2" />
          Download All
        </Button>
      </div>
    </div>
  )
}

export default StoryDetailPage
