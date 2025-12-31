import { Code2, Headphones, Sparkles, Github } from 'lucide-react'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Badge, Progress } from '@/components/ui'

export function HomePage() {
  return (
    <>
      {/* Hero Section */}
      <section className="pt-16 pb-20 px-6">
        <div className="container mx-auto text-center max-w-4xl">
          <Badge variant="secondary" className="mb-6">
            <Sparkles className="h-3 w-3 mr-1" />
            Powered by AI
          </Badge>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-6">
            Transform Code into
            <span className="text-primary"> Compelling Stories</span>
          </h1>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Turn any GitHub repository into engaging audio narratives.
            Understand codebases through storytelling, not documentation.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Button size="lg" className="gap-2">
              <Github className="h-4 w-4" />
              Connect Repository
            </Button>
            <Button size="lg" variant="outline">
              <Headphones className="h-4 w-4 mr-2" />
              Listen to Demo
            </Button>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-6 bg-card/30">
        <div className="container mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">
            How It Works
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Github className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Connect Repository</CardTitle>
                <CardDescription>
                  Paste any GitHub URL and we'll analyze the codebase structure
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Sparkles className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>AI Narrates</CardTitle>
                <CardDescription>
                  Our agents create a compelling narrative tailored to your learning style
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Headphones className="h-5 w-5 text-primary" />
                </div>
                <CardTitle>Listen & Learn</CardTitle>
                <CardDescription>
                  Audio stories you can enjoy anywhere — commute, gym, or relaxing
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* Demo Card */}
      <section className="py-20 px-6">
        <div className="container mx-auto max-w-2xl">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code2 className="h-5 w-5 text-primary" />
                shadcn/ui
              </CardTitle>
              <CardDescription>
                Beautifully designed components built with Radix UI and Tailwind CSS
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Generating story...</span>
                <span>75%</span>
              </div>
              <Progress value={75} className="h-2" />
              <div className="flex gap-2 flex-wrap">
                <Badge>React</Badge>
                <Badge variant="secondary">TypeScript</Badge>
                <Badge variant="outline">Tailwind</Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </>
  )
}

export default HomePage
