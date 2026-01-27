"use client"

import { useState } from 'react'
import { ModelSelector } from '@/components/ModelSelector'

export default function DesignPage() {
  const [config, setConfig] = useState({
    gameType: 'standard',
    rounds: 10,
    wordCountMin: 30,
    wordCountMax: 100,
    storytellerModel: 'claude-sonnet-4-5-20250929',
    judgeModel: 'claude-sonnet-4-5-20250929',
    storytellerTemp: 1.0,
    judgeTemp: 1.0,
    storytellerStrategy: 'baseline',
    judgeStrategy: 'adversarial',
    factCategories: [] as string[],
  })

  const gameTypes = [
    { value: 'standard', label: 'Standard (2 Truths + 1 Lie)' },
    { value: 'all_truth', label: 'All Truth (3 Truths)' },
    { value: 'all_lies', label: 'All Lies (3 Lies)' },
    { value: 'majority_lies', label: 'Majority Lies (2 Lies + 1 Truth)' },
  ]

  const storytellerStrategies = [
    'baseline', 'level_k_0', 'level_k_1', 'level_k_2',
    'source_heavy', 'source_light', 'detail_granular', 'detail_general',
    'style_logical', 'style_emotional'
  ]

  const judgeStrategies = ['adversarial', 'curious', 'verification', 'intuitive']

  const factCategories = [
    'science', 'history', 'biology', 'geography', 'technology',
    'culture', 'sports', 'arts', 'literature', 'medicine'
  ]

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-6">Experiment Configuration</h2>

        {/* Game Setup Section */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Game Setup</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Game Type
              </label>
              <select
                value={config.gameType}
                onChange={(e) => setConfig({ ...config, gameType: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {gameTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Rounds
              </label>
              <input
                type="number"
                value={config.rounds}
                onChange={(e) => setConfig({ ...config, rounds: parseInt(e.target.value) })}
                min="1"
                max="1000"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Min Word Count
              </label>
              <input
                type="number"
                value={config.wordCountMin}
                onChange={(e) => setConfig({ ...config, wordCountMin: parseInt(e.target.value) })}
                min="10"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Max Word Count
              </label>
              <input
                type="number"
                value={config.wordCountMax}
                onChange={(e) => setConfig({ ...config, wordCountMax: parseInt(e.target.value) })}
                min="10"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Model Selection Section */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Model Selection</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <ModelSelector
                value={config.storytellerModel}
                onChange={(model) => setConfig({ ...config, storytellerModel: model })}
                label="Storyteller Model"
                showPopular={true}
              />
              <div className="mt-2">
                <label className="block text-sm text-gray-600 mb-1">
                  Temperature: {config.storytellerTemp}
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.storytellerTemp}
                  onChange={(e) => setConfig({ ...config, storytellerTemp: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>

            <div>
              <ModelSelector
                value={config.judgeModel}
                onChange={(model) => setConfig({ ...config, judgeModel: model })}
                label="Judge Model"
                showPopular={true}
              />
              <div className="mt-2">
                <label className="block text-sm text-gray-600 mb-1">
                  Temperature: {config.judgeTemp}
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.judgeTemp}
                  onChange={(e) => setConfig({ ...config, judgeTemp: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Strategy Section */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Strategy & Style</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Storyteller Strategy
              </label>
              <select
                value={config.storytellerStrategy}
                onChange={(e) => setConfig({ ...config, storytellerStrategy: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {storytellerStrategies.map((strategy) => (
                  <option key={strategy} value={strategy}>
                    {strategy.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Judge Question Style
              </label>
              <select
                value={config.judgeStrategy}
                onChange={(e) => setConfig({ ...config, judgeStrategy: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {judgeStrategies.map((strategy) => (
                  <option key={strategy} value={strategy}>
                    {strategy.charAt(0).toUpperCase() + strategy.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Fact Categories */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Content</h3>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Fact Categories (select multiple)
          </label>
          <div className="grid grid-cols-5 gap-2">
            {factCategories.map((category) => (
              <label key={category} className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.factCategories.includes(category)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setConfig({ ...config, factCategories: [...config.factCategories, category] })
                    } else {
                      setConfig({ ...config, factCategories: config.factCategories.filter(c => c !== category) })
                    }
                  }}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm">{category}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between items-center pt-4 border-t">
          <div className="space-x-2">
            <button className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200">
              Load Preset
            </button>
            <button className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200">
              Save Preset
            </button>
          </div>
          <button className="px-6 py-2 text-white bg-blue-600 rounded-md hover:bg-blue-700">
            Start Experiment
          </button>
        </div>
      </div>
    </div>
  )
}
