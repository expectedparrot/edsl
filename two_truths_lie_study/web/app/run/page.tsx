"use client"

import { useState } from 'react'

type ExperimentPhase = 'idle' | 'story' | 'questions' | 'verdict' | 'complete'

export default function RunPage() {
  const [isRunning, setIsRunning] = useState(false)
  const [phase, setPhase] = useState<ExperimentPhase>('idle')
  const [currentRound, setCurrentRound] = useState(0)
  const [totalRounds, setTotalRounds] = useState(10)
  const [logs, setLogs] = useState<string[]>([])

  const startExperiment = () => {
    setIsRunning(true)
    setCurrentRound(1)
    setPhase('story')
    setLogs(['Experiment started...', 'Generating stories...'])
  }

  const stopExperiment = () => {
    setIsRunning(false)
    setPhase('idle')
    setLogs([...logs, 'Experiment stopped by user'])
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Control Panel */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold mb-2">Live Experiment Execution</h2>
            <p className="text-gray-600">
              {isRunning ? `Round ${currentRound} of ${totalRounds}` : 'Ready to start'}
            </p>
          </div>
          <div className="flex space-x-3">
            {!isRunning ? (
              <button
                onClick={startExperiment}
                className="px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center space-x-2"
              >
                <span>▶️</span>
                <span>Start</span>
              </button>
            ) : (
              <>
                <button
                  onClick={() => setIsRunning(false)}
                  className="px-6 py-3 bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
                >
                  ⏸ Pause
                </button>
                <button
                  onClick={stopExperiment}
                  className="px-6 py-3 bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  ⏹ Stop
                </button>
              </>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {isRunning && (
          <div className="mt-4">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(currentRound / totalRounds) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Phase Indicators */}
      {isRunning && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center justify-between">
            {(['story', 'questions', 'verdict'] as ExperimentPhase[]).map((p, i) => (
              <div key={p} className="flex items-center">
                <div
                  className={`flex items-center justify-center w-12 h-12 rounded-full ${
                    phase === p
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-600'
                  }`}
                >
                  {i + 1}
                </div>
                <span className="ml-3 text-sm font-medium capitalize">{p}</span>
                {i < 2 && <div className="w-24 h-1 bg-gray-200 mx-4" />}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Stream Panel */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Live Output</h3>
        <div className="space-y-4">
          {phase === 'story' && isRunning && (
            <div className="p-4 bg-blue-50 rounded-md border border-blue-200">
              <div className="flex items-center space-x-2 mb-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                <span className="font-medium text-blue-900">Generating Stories...</span>
              </div>
              <div className="text-sm text-gray-700 space-y-2 mt-3">
                <p><strong>Story 1:</strong> In 1969, Apollo 11 successfully landed humans on the moon...</p>
                <p><strong>Story 2:</strong> The Great Wall of China is visible from space with the naked eye...</p>
                <p><strong>Story 3:</strong> Honey never spoils and has been found edible in ancient Egyptian tombs...</p>
              </div>
            </div>
          )}

          {phase === 'questions' && isRunning && (
            <div className="space-y-3">
              <div className="p-4 bg-purple-50 rounded-md border border-purple-200">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="font-medium text-purple-900">Judge Question:</span>
                </div>
                <p className="text-sm text-gray-700">Can you provide more details about the Apollo 11 mission?</p>
              </div>
              <div className="p-4 bg-green-50 rounded-md border border-green-200">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="font-medium text-green-900">Storyteller Answer:</span>
                </div>
                <p className="text-sm text-gray-700">The mission launched on July 16, 1969, with Neil Armstrong, Buzz Aldrin, and Michael Collins...</p>
              </div>
            </div>
          )}

          {phase === 'verdict' && isRunning && (
            <div className="p-4 bg-yellow-50 rounded-md border border-yellow-200">
              <div className="flex items-center space-x-2 mb-2">
                <span className="font-medium text-yellow-900">Final Verdict:</span>
              </div>
              <p className="text-sm text-gray-700">
                <strong>Identified Lie:</strong> Story 2 (The Great Wall claim)
              </p>
              <p className="text-sm text-gray-600 mt-2">
                <strong>Confidence:</strong> 85%
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Round Summary Cards */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Completed Rounds</h3>
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((round) => (
            <div key={round} className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">Round {round}</span>
                <span className="text-2xl">✅</span>
              </div>
              <div className="text-sm text-gray-600">
                <p>Detection: Correct</p>
                <p>Confidence: 87%</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Technical Logs */}
      <div className="bg-white rounded-lg shadow p-6">
        <details>
          <summary className="text-lg font-semibold cursor-pointer">Technical Logs</summary>
          <div className="mt-4 bg-gray-900 text-green-400 p-4 rounded-md font-mono text-xs max-h-64 overflow-y-auto">
            {logs.map((log, i) => (
              <div key={i}>{log}</div>
            ))}
          </div>
        </details>
      </div>
    </div>
  )
}
