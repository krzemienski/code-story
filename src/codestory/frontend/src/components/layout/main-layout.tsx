import type { ReactNode } from 'react'
import { Code2 } from 'lucide-react'
import { Button } from '@/components/ui'

interface MainLayoutProps {
  children: ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="min-h-screen bg-background text-foreground scrollbar-elegant">
      {/* Navigation */}
      <header className="border-b border-border/40 backdrop-blur-sm fixed w-full z-50 bg-background/80">
        <nav className="container mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <Code2 className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg">Code Story</span>
          </a>
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm">Features</Button>
            <Button variant="ghost" size="sm">Pricing</Button>
            <Button variant="ghost" size="sm">Docs</Button>
            <Button size="sm">Get Started</Button>
          </div>
        </nav>
      </header>

      {/* Main Content */}
      <main className="pt-16">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 py-8 px-6 mt-auto">
        <div className="container mx-auto text-center text-sm text-muted-foreground">
          <p>Code Story — Transform code into stories</p>
        </div>
      </footer>
    </div>
  )
}

export default MainLayout
