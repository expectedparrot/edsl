"use client"

import { useState, useMemo } from 'react'
import { useModels, type ModelInfo } from '@/lib/hooks/useModels'
import { SERVICE_DISPLAY_NAMES, SERVICE_COLORS } from '@/config/models'

interface ModelSelectorProps {
  value: string
  onChange: (model: string) => void
  label?: string
  showPopular?: boolean
  groupByService?: boolean
  className?: string
}

/**
 * Service badge component for displaying model provider.
 */
function ServiceBadge({ service }: { service: string }) {
  const displayName = SERVICE_DISPLAY_NAMES[service] || service
  const colorClass = SERVICE_COLORS[service] || "bg-gray-100 text-gray-800"

  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${colorClass}`}>
      {displayName}
    </span>
  )
}

/**
 * Searchable model selector dropdown with service badges.
 *
 * Features:
 * - Live search/filter by model name
 * - Service provider badges
 * - Popular models quick access
 * - Grouped view by service (optional)
 * - Handles 400+ models efficiently
 */
export function ModelSelector({
  value,
  onChange,
  label = "Model",
  showPopular = true,
  groupByService = false,
  className = ""
}: ModelSelectorProps) {
  const { models, grouped, popular, isLoading, error } = useModels()
  const [searchQuery, setSearchQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)

  // Filter models by search query
  const filteredModels = useMemo(() => {
    if (!searchQuery) return models
    const query = searchQuery.toLowerCase()
    return models.filter(m =>
      m.name.toLowerCase().includes(query) ||
      m.service.toLowerCase().includes(query)
    )
  }, [models, searchQuery])

  // Group filtered models by service if requested
  const groupedFiltered = useMemo(() => {
    if (!groupByService) return null

    const groups: Record<string, ModelInfo[]> = {}
    for (const model of filteredModels) {
      if (!groups[model.service]) {
        groups[model.service] = []
      }
      groups[model.service].push(model)
    }
    return groups
  }, [filteredModels, groupByService])

  // Get popular models that are actually available
  const popularModels = useMemo(() => {
    if (!showPopular) return []
    const modelNames = new Set(models.map(m => m.name))
    return popular.filter(name => modelNames.has(name))
  }, [models, popular, showPopular])

  // Find selected model info
  const selectedModel = models.find(m => m.name === value)

  const handleSelect = (modelName: string) => {
    onChange(modelName)
    setIsOpen(false)
    setSearchQuery('')
  }

  if (isLoading) {
    return (
      <div className={className}>
        <label className="block text-sm font-medium mb-1">{label}</label>
        <div className="border rounded p-2 bg-gray-50 animate-pulse">
          Loading models...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={className}>
        <label className="block text-sm font-medium mb-1">{label}</label>
        <div className="border rounded p-2 bg-yellow-50 text-yellow-800 text-sm">
          ⚠️ Using fallback models (API unavailable)
        </div>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full mt-1 border rounded p-2"
        >
          {popularModels.map(name => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
      </div>
    )
  }

  return (
    <div className={`relative ${className}`}>
      <label className="block text-sm font-medium mb-1">{label}</label>

      {/* Selected model display */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full border rounded p-2 bg-white text-left flex items-center justify-between hover:bg-gray-50"
      >
        <div className="flex items-center gap-2">
          {selectedModel ? (
            <>
              <ServiceBadge service={selectedModel.service} />
              <span className="text-sm">{selectedModel.name}</span>
            </>
          ) : (
            <span className="text-sm text-gray-500">Select a model...</span>
          )}
        </div>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border rounded shadow-lg max-h-96 overflow-hidden flex flex-col">
          {/* Search box */}
          <div className="p-2 border-b">
            <input
              type="text"
              placeholder="Search models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-1.5 border rounded text-sm"
              autoFocus
            />
          </div>

          {/* Popular models section */}
          {showPopular && !searchQuery && popularModels.length > 0 && (
            <div className="border-b">
              <div className="px-3 py-2 bg-gray-50 text-xs font-semibold text-gray-600">
                POPULAR MODELS
              </div>
              {popularModels.map(name => {
                const model = models.find(m => m.name === name)
                if (!model) return null
                return (
                  <button
                    key={name}
                    onClick={() => handleSelect(name)}
                    className="w-full px-3 py-2 text-left hover:bg-blue-50 flex items-center gap-2 text-sm"
                  >
                    <ServiceBadge service={model.service} />
                    <span>{name}</span>
                  </button>
                )
              })}
            </div>
          )}

          {/* Model list */}
          <div className="overflow-y-auto flex-1">
            {groupedFiltered ? (
              // Grouped view
              Object.entries(groupedFiltered)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([service, serviceModels]) => (
                  <div key={service}>
                    <div className="px-3 py-2 bg-gray-50 text-xs font-semibold text-gray-600 sticky top-0">
                      {SERVICE_DISPLAY_NAMES[service] || service.toUpperCase()} ({serviceModels.length})
                    </div>
                    {serviceModels.map(model => (
                      <button
                        key={model.name}
                        onClick={() => handleSelect(model.name)}
                        className={`w-full px-3 py-2 text-left hover:bg-blue-50 text-sm ${
                          model.name === value ? 'bg-blue-100' : ''
                        }`}
                      >
                        {model.name}
                      </button>
                    ))}
                  </div>
                ))
            ) : (
              // Flat view
              filteredModels.length > 0 ? (
                filteredModels.map(model => (
                  <button
                    key={model.name}
                    onClick={() => handleSelect(model.name)}
                    className={`w-full px-3 py-2 text-left hover:bg-blue-50 flex items-center gap-2 text-sm ${
                      model.name === value ? 'bg-blue-100' : ''
                    }`}
                  >
                    <ServiceBadge service={model.service} />
                    <span>{model.name}</span>
                  </button>
                ))
              ) : (
                <div className="px-3 py-4 text-center text-sm text-gray-500">
                  No models match "{searchQuery}"
                </div>
              )
            )}
          </div>

          {/* Footer with count */}
          <div className="px-3 py-2 border-t bg-gray-50 text-xs text-gray-600">
            {filteredModels.length} model{filteredModels.length !== 1 ? 's' : ''} available
          </div>
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  )
}
