"use client"

import { useState } from 'react'

type Experiment = {
  id: string
  timestamp: string
  storytellerModel: string
  judgeModel: string
  rounds: number
  accuracy: number
  avgConfidence: number
}

export default function ResultsPage() {
  const [experiments] = useState<Experiment[]>([
    {
      id: 'exp-001',
      timestamp: '2026-01-18 14:30',
      storytellerModel: 'claude-sonnet-4-5',
      judgeModel: 'gpt-4o',
      rounds: 10,
      accuracy: 87,
      avgConfidence: 0.82,
    },
    {
      id: 'exp-002',
      timestamp: '2026-01-18 13:15',
      storytellerModel: 'gpt-4o',
      judgeModel: 'claude-sonnet-4-5',
      rounds: 10,
      accuracy: 73,
      avgConfidence: 0.68,
    },
  ])

  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null)

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">Experiment Results</h2>
          <button className="px-4 py-2 text-sm text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50">
            Export Data
          </button>
        </div>

        {/* Experiment List */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Previous Runs</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Storyteller
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Judge
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Rounds
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Accuracy
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {experiments.map((exp) => (
                  <tr key={exp.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {exp.id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {exp.timestamp}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {exp.storytellerModel}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {exp.judgeModel}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {exp.rounds}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        exp.accuracy >= 80 ? 'bg-green-100 text-green-800' :
                        exp.accuracy >= 60 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {exp.accuracy}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <button
                        onClick={() => setSelectedExperiment(exp.id)}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Aggregate Statistics */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Aggregate Statistics</h3>
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">Total Experiments</div>
              <div className="text-3xl font-bold text-blue-900">{experiments.length}</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">Avg Accuracy</div>
              <div className="text-3xl font-bold text-green-900">
                {Math.round(experiments.reduce((sum, e) => sum + e.accuracy, 0) / experiments.length)}%
              </div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">Best Judge</div>
              <div className="text-xl font-bold text-purple-900">Claude Sonnet 4.5</div>
            </div>
            <div className="bg-orange-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">Best Fibber</div>
              <div className="text-xl font-bold text-orange-900">GPT-4o</div>
            </div>
          </div>
        </div>

        {/* Confidence Calibration Chart Placeholder */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Confidence Calibration</h3>
          <div className="bg-gray-100 h-64 rounded-lg flex items-center justify-center">
            <span className="text-gray-500">Chart visualization will go here</span>
          </div>
        </div>

        {/* Round Inspector */}
        {selectedExperiment && (
          <div className="border-t pt-8">
            <h3 className="text-lg font-semibold mb-4">Round Inspector: {selectedExperiment}</h3>
            <div className="bg-gray-50 p-6 rounded-lg">
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium mb-2">Stories</h4>
                  <div className="space-y-2">
                    <div className="p-3 bg-white rounded border">
                      <strong>Story 1 (Truth):</strong> The Eiffel Tower can be 15 cm taller during summer...
                    </div>
                    <div className="p-3 bg-white rounded border border-red-300 bg-red-50">
                      <strong>Story 2 (LIE):</strong> The Great Wall of China is visible from space...
                    </div>
                    <div className="p-3 bg-white rounded border">
                      <strong>Story 3 (Truth):</strong> Bananas are berries but strawberries are not...
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium mb-2">Q&A Transcript</h4>
                  <div className="p-3 bg-white rounded border space-y-2 text-sm">
                    <p><strong>Judge:</strong> Can you provide sources for the Great Wall claim?</p>
                    <p><strong>Storyteller:</strong> This is a common misconception that has been debunked by NASA...</p>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium mb-2">Verdict</h4>
                  <div className="p-3 bg-green-50 rounded border border-green-300">
                    <p><strong>Identified:</strong> Story 2</p>
                    <p><strong>Confidence:</strong> 92%</p>
                    <p className="mt-2 text-sm"><strong>Reasoning:</strong> The storyteller showed hesitation and the claim contradicts established scientific facts.</p>
                  </div>
                </div>
              </div>

              <div className="mt-4">
                <button
                  onClick={() => setSelectedExperiment(null)}
                  className="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
