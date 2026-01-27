"use client"

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const tabs = [
  { name: 'Design', href: '/design', icon: '📋', description: 'Configure experiment' },
  { name: 'Run', href: '/run', icon: '▶️', description: 'Execute live' },
  { name: 'Results', href: '/results', icon: '📊', description: 'Analyze data' },
  { name: 'Human Play', href: '/human-play', icon: '👤', description: 'Coming soon' },
]

export function TabNavigation() {
  const pathname = usePathname()

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">🎭</span>
            <h1 className="text-xl font-bold text-gray-900">Why Would I Lie</h1>
          </div>
          <nav className="flex space-x-8">
            {tabs.map((tab) => {
              const isActive = pathname === tab.href
              return (
                <Link
                  key={tab.name}
                  href={tab.href}
                  className={cn(
                    'inline-flex items-center px-3 py-2 border-b-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  )}
                  title={tab.description}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.name}
                </Link>
              )
            })}
          </nav>
        </div>
      </div>
    </div>
  )
}
