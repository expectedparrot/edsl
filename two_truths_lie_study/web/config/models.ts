/**
 * Curated list of popular/recommended LLM models.
 *
 * These models are shown prominently in the UI for quick access.
 */
export const POPULAR_MODELS = [
  "claude-opus-4-5-20251101",      // Latest Claude Opus
  "claude-sonnet-4-5-20250929",    // Latest Claude Sonnet
  "gpt-4-turbo",                   // Latest GPT-4 Turbo
  "chatgpt-4o-latest",             // GPT-4o
  "gemini-2.5-flash",              // Latest Gemini Flash
  "claude-3-7-sonnet-20250219",    // Fast, capable Claude
]

/**
 * Service provider display names.
 */
export const SERVICE_DISPLAY_NAMES: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
  mistral: "Mistral",
  groq: "Groq",
  deep_infra: "Deep Infra",
  together: "Together AI",
  bedrock: "AWS Bedrock",
  xai: "xAI",
  perplexity: "Perplexity",
  deepseek: "DeepSeek",
  azure: "Azure OpenAI",
}

/**
 * Service provider colors for badges.
 */
export const SERVICE_COLORS: Record<string, string> = {
  anthropic: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  openai: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  google: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  mistral: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  groq: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  deep_infra: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
  together: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
  bedrock: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  xai: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
  perplexity: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  deepseek: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200",
  azure: "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200",
}
