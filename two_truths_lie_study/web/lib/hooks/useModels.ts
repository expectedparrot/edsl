"use client"

import { useState, useEffect } from 'react'

export interface ModelInfo {
  name: string
  service: string
}

export interface ModelsData {
  models: ModelInfo[]
  grouped: Record<string, string[]>
  popular: string[]
  last_updated: string | null
}

export interface UseModelsReturn {
  models: ModelInfo[]
  grouped: Record<string, string[]>
  popular: string[]
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

const FALLBACK_MODELS: ModelInfo[] = [
  { name: "claude-opus-4-5-20251101", service: "anthropic" },
  { name: "claude-sonnet-4-5-20250929", service: "anthropic" },
  { name: "gpt-4-turbo", service: "openai" },
  { name: "chatgpt-4o-latest", service: "openai" },
  { name: "gemini-2.5-flash", service: "google" },
]

const FALLBACK_POPULAR = [
  "claude-opus-4-5-20251101",
  "claude-sonnet-4-5-20250929",
  "gpt-4-turbo",
  "chatgpt-4o-latest",
  "gemini-2.5-flash",
]

/**
 * React hook for fetching and managing LLM models from backend API.
 *
 * Fetches models on mount and provides loading/error states.
 * Falls back to hardcoded popular models if API unavailable.
 */
export function useModels(): UseModelsReturn {
  const [models, setModels] = useState<ModelInfo[]>(FALLBACK_MODELS)
  const [grouped, setGrouped] = useState<Record<string, string[]>>({})
  const [popular, setPopular] = useState<string[]>(FALLBACK_POPULAR)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchModels = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/config/models`)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data: ModelsData = await response.json()

      setModels(data.models || FALLBACK_MODELS)
      setGrouped(data.grouped || {})
      setPopular(data.popular || FALLBACK_POPULAR)
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err))
      setError(error)
      console.error('Failed to fetch models:', error)

      // Keep fallback models on error
      setModels(FALLBACK_MODELS)
      setPopular(FALLBACK_POPULAR)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchModels()
  }, [])

  return {
    models,
    grouped,
    popular,
    isLoading,
    error,
    refetch: fetchModels
  }
}
