import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mammoth from 'mammoth'

const API_BASE = '/api'

function App() {
  const [apps, setApps] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const chatEndRef = useRef(null)

  useEffect(() => {
    fetchApps()
  }, [])

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchApps = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE}/apps`)
      if (!response.ok) throw new Error('Failed to fetch apps')
      const data = await response.json()
      setApps(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAppSelect = (app) => {
    setMessages(prev => [...prev, {
      type: 'app-selected',
      app: app,
      timestamp: new Date().toISOString()
    }])
  }

  const handleFormSubmit = async (app, formData) => {
    // Add user input message (right side)
    setMessages(prev => [...prev, {
      type: 'user-input',
      app: app,
      data: formData,
      timestamp: new Date().toISOString()
    }])

    // Add loading message (left side)
    setMessages(prev => [...prev, {
      type: 'loading',
      timestamp: new Date().toISOString()
    }])

    // Execute and replace loading with result
    await executeApp(app, formData)
  }

  const executeApp = async (app, formData) => {
    try {
      const response = await fetch(`${API_BASE}/apps/${app.app_id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: formData })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Execution failed')
      }

      const result = await response.json()

      // Replace loading message with result
      if (result.status === 'failed') {
        setMessages(prev => prev.map((msg, idx) =>
          msg.type === 'loading' && idx === prev.length - 1
            ? { type: 'error', data: result.error, timestamp: new Date().toISOString() }
            : msg
        ))
      } else {
        setMessages(prev => prev.map((msg, idx) =>
          msg.type === 'loading' && idx === prev.length - 1
            ? {
                type: 'assistant-response',
                app: app,
                data: result,
                originalInput: formData,
                selectedFormatter: null,
                timestamp: new Date().toISOString()
              }
            : msg
        ))
      }
    } catch (err) {
      // Replace loading message with error
      setMessages(prev => prev.map((msg, idx) =>
        msg.type === 'loading' && idx === prev.length - 1
          ? { type: 'error', data: err.message, timestamp: new Date().toISOString() }
          : msg
      ))
    }
  }

  const handleFormatterSelect = async (messageIndex, app, formData, formatterName) => {
    try {
      const response = await fetch(`${API_BASE}/apps/${app.app_id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: formData,
          formatter_name: formatterName
        })
      })

      if (!response.ok) throw new Error('Formatter execution failed')

      const result = await response.json()

      setMessages(prev => prev.map((msg, idx) =>
        idx === messageIndex ? { ...msg, data: result, selectedFormatter: formatterName } : msg
      ))
    } catch (err) {
      console.error('Formatter error:', err)
    }
  }

  const handleNewInput = () => {
    setMessages(prev => [...prev, {
      type: 'app-selector',
      timestamp: new Date().toISOString()
    }])
  }

  const handleClearAllApps = async () => {
    if (!window.confirm('Are you sure you want to delete ALL apps from the server? This cannot be undone.')) {
      return
    }

    try {
      setLoading(true)
      // Get all apps
      const response = await fetch(`${API_BASE}/apps`)
      if (!response.ok) throw new Error('Failed to fetch apps')
      const allApps = await response.json()

      // Delete each app
      let deleted = 0
      for (const app of allApps) {
        const deleteResponse = await fetch(`${API_BASE}/apps/${app.app_id}`, {
          method: 'DELETE'
        })
        if (deleteResponse.ok) {
          deleted++
        }
      }

      // Refresh the apps list
      await fetchApps()
      alert(`Successfully deleted ${deleted} app${deleted !== 1 ? 's' : ''}`)
    } catch (err) {
      alert('Error clearing apps: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="container"><div className="loading">Loading apps...</div></div>
  }

  if (error) {
    return (
      <div className="container">
        <div className="error">Error: {error}</div>
        <button onClick={fetchApps} className="back-button">Retry</button>
      </div>
    )
  }

  return (
    <div className="chat-app">
      <div className="chat-header">
        <div className="header-content">
          <div>
            <h1>EDSL Apps</h1>
            <p>{apps.length} app{apps.length !== 1 ? 's' : ''} available</p>
          </div>
          <button onClick={handleClearAllApps} className="clear-apps-button" disabled={loading || apps.length === 0}>
            🗑️ Clear All Apps
          </button>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="message-container assistant">
            <div className="message-content">
              <AppSearchSelector apps={apps} onAppSelect={handleAppSelect} />
            </div>
          </div>
        )}

        {messages.map((message, idx) => (
          <ChatMessage
            key={idx}
            message={message}
            messageIndex={idx}
            apps={apps}
            onAppSelect={handleAppSelect}
            onFormSubmit={handleFormSubmit}
            onFormatterSelect={handleFormatterSelect}
          />
        ))}

        <div ref={chatEndRef} />
      </div>

      {messages.length > 0 && (
        <div className="chat-input-container">
          <button onClick={handleNewInput} className="new-input-button">
            + New Input
          </button>
        </div>
      )}
    </div>
  )
}

function ChatMessage({ message, messageIndex, apps, onAppSelect, onFormSubmit, onFormatterSelect }) {
  if (message.type === 'loading') {
    return (
      <div className="message-container assistant">
        <div className="message-content loading-message">
          <div className="spinner"></div>
          <span>Running...</span>
        </div>
      </div>
    )
  }

  if (message.type === 'app-selector') {
    return (
      <div className="message-container assistant">
        <div className="message-content">
          <AppSearchSelector apps={apps} onAppSelect={onAppSelect} />
        </div>
      </div>
    )
  }

  if (message.type === 'app-selected') {
    return (
      <div className="message-container user">
        <div className="message-content form-message">
          <div className="app-selected-header">
            <strong>{message.app.name?.name || message.app.name}</strong>
            <p>{message.app.description?.short || message.app.description}</p>
          </div>
          <InputForm app={message.app} onSubmit={onFormSubmit} />
        </div>
      </div>
    )
  }

  if (message.type === 'user-input') {
    return (
      <div className="message-container user">
        <div className="message-content user-message">
          <div className="input-summary">
            {Object.entries(message.data).map(([key, value]) => (
              <div key={key} className="input-item">
                <span className="input-label">{key}:</span>{' '}
                <span className="input-value">
                  {Array.isArray(value) ? value.join(', ') : String(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (message.type === 'assistant-response') {
    const [docxPreview, setDocxPreview] = useState(null)
    const [showingPreview, setShowingPreview] = useState(false)
    const [showPushModal, setShowPushModal] = useState(false)
    const [pushFormData, setPushFormData] = useState({
      visibility: 'unlisted',
      alias: '',
      description: ''
    })
    const [pushing, setPushing] = useState(false)
    const [pushResult, setPushResult] = useState(null)

    const isFile = message.data.result &&
                   typeof message.data.result === 'object' &&
                   message.data.result.base64_string

    // Get the output_type for the selected formatter (or default if none selected)
    const currentFormatter = message.selectedFormatter || message.app.default_formatter_name || message.app.available_formatters?.[0]
    const formatterMeta = message.app.formatter_metadata?.find(f => f.name === currentFormatter)
    const outputType = formatterMeta?.output_type || 'auto'

    const isDocx = isFile && message.data.result.path?.endsWith('.docx')
    const isEdslObject = outputType === 'edsl_object' && typeof message.data.result === 'object' && (message.data.result.object_type || message.data.result.edsl_class_name)

    useEffect(() => {
      if (isDocx && !docxPreview) {
        // Extract preview from docx
        const base64 = message.data.result.base64_string
        const byteCharacters = atob(base64)
        const byteNumbers = new Array(byteCharacters.length)
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i)
        }
        const byteArray = new Uint8Array(byteNumbers)
        const arrayBuffer = byteArray.buffer

        mammoth.convertToHtml({ arrayBuffer })
          .then(result => {
            setDocxPreview(result.value)
          })
          .catch(err => {
            console.error('Failed to preview docx:', err)
          })
      }
    }, [isDocx, message.data.result])

    const isCSV = typeof message.data.result === 'string' &&
                  message.data.result.includes(',') &&
                  (message.data.result.startsWith('answer.') || message.data.result.match(/^[^,\n]+,[^,\n]+/))

    const parseCSV = (csvText) => {
      const lines = csvText.trim().split('\n')
      if (lines.length === 0) return { headers: [], rows: [] }

      const headers = lines[0].split(',').map(h => h.trim())
      const rows = lines.slice(1).map(line => {
        // Simple CSV parsing - doesn't handle quotes perfectly but works for basic cases
        return line.split(',').map(cell => cell.trim())
      })

      return { headers, rows }
    }

    const handleDownload = () => {
      const result = message.data.result
      const base64 = result.base64_string
      const filename = result.path ? result.path.split('/').pop() : 'download.docx'

      // Convert base64 to blob
      const byteCharacters = atob(base64)
      const byteNumbers = new Array(byteCharacters.length)
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
      }
      const byteArray = new Uint8Array(byteNumbers)
      const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })

      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }

    const handlePushToCoop = async () => {
      setPushing(true)
      setPushResult(null)
      try {
        const response = await fetch(`${API_BASE}/push-object`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            object_dict: message.data.result,
            visibility: pushFormData.visibility,
            alias: pushFormData.alias || undefined,
            description: pushFormData.description || undefined
          })
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Push failed')
        }

        const result = await response.json()
        setPushResult({ success: true, message: result.message, data: result.result })
      } catch (err) {
        setPushResult({ success: false, message: err.message })
      } finally {
        setPushing(false)
      }
    }

    return (
      <div className="message-container assistant">
        <div className="message-content">
          <div className="formatter-selector">
            <strong>Format:</strong>
            {message.app.available_formatters.map(formatter => {
              const meta = message.app.formatter_metadata?.find(f => f.name === formatter)
              const outputType = meta?.output_type || 'auto'

              // Determine type badge and color
              let typeBadge = ''
              let typeClass = ''
              if (outputType === 'markdown') {
                typeBadge = 'MD'
                typeClass = 'type-markdown'
              } else if (outputType === 'file' || formatter.includes('docx') || formatter.includes('pdf')) {
                typeBadge = '📄'
                typeClass = 'type-file'
              } else if (outputType === 'edsl_object' || formatter.includes('survey') || formatter.includes('scenario') || formatter.includes('agent')) {
                typeBadge = '🔧'
                typeClass = 'type-edsl'
              } else if (formatter === 'raw_results') {
                typeBadge = 'JSON'
                typeClass = 'type-json'
              }

              const isSelected = message.selectedFormatter === formatter
              const isDefault = !message.selectedFormatter && formatter === message.app.default_formatter_name

              return (
                <button
                  key={formatter}
                  onClick={() => onFormatterSelect(messageIndex, message.app, message.originalInput, formatter)}
                  className={`formatter-chip ${isSelected || isDefault ? 'selected' : ''} ${typeClass}`}
                >
                  {typeBadge && <span className="type-badge">{typeBadge}</span>}
                  {formatter}
                </button>
              )
            })}
          </div>

          {message.data.result && (
            <div className="response-result">
              {isFile ? (
                <div className="file-result">
                  <div className="file-info">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                    <div>
                      <strong>{message.data.result.path ? message.data.result.path.split('/').pop() : 'Document'}</strong>
                      <p>Ready to download</p>
                    </div>
                  </div>
                  <button onClick={handleDownload} className="download-button">
                    Download File
                  </button>

                  {isDocx && docxPreview && (
                    <div className="docx-preview-container">
                      <div className="preview-header">
                        <button
                          onClick={() => setShowingPreview(!showingPreview)}
                          className="preview-toggle"
                        >
                          {showingPreview ? '▼ Hide Preview' : '▶ Show Preview'}
                        </button>
                      </div>
                      {showingPreview && (
                        <div
                          className="docx-preview"
                          dangerouslySetInnerHTML={{ __html: docxPreview }}
                        />
                      )}
                    </div>
                  )}
                </div>
              ) : isCSV ? (
                <div className="csv-table-container">
                  {(() => {
                    const { headers, rows } = parseCSV(message.data.result)
                    return (
                      <table className="csv-table">
                        <thead>
                          <tr>
                            {headers.map((header, idx) => (
                              <th key={idx}>{header}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((row, rowIdx) => (
                            <tr key={rowIdx}>
                              {row.map((cell, cellIdx) => (
                                <td key={cellIdx}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  })()}
                </div>
              ) : isEdslObject ? (
                <div className="edsl-object-result">
                  <div className="edsl-object-header">
                    <div className="edsl-object-info">
                      <span className="edsl-badge">
                        {(message.data.result.object_type || message.data.result.edsl_class_name || 'EDSL').replace('_', ' ').toUpperCase()}
                      </span>
                      <span className="edsl-object-summary">
                        EDSL {(message.data.result.object_type || message.data.result.edsl_class_name || 'object').replace('_', ' ')} created
                      </span>
                    </div>
                    <button
                      onClick={() => setShowPushModal(true)}
                      className="push-button"
                    >
                      📤 Push to Coop
                    </button>
                  </div>

                  {showPushModal && (
                    <div className="push-modal-overlay" onClick={() => setShowPushModal(false)}>
                      <div className="push-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>Push to Coop</h3>
                        <div className="push-form">
                          <div className="form-group">
                            <label>Visibility</label>
                            <select
                              value={pushFormData.visibility}
                              onChange={(e) => setPushFormData({...pushFormData, visibility: e.target.value})}
                            >
                              <option value="unlisted">Unlisted</option>
                              <option value="public">Public</option>
                              <option value="private">Private</option>
                            </select>
                          </div>
                          <div className="form-group">
                            <label>Alias (optional)</label>
                            <input
                              type="text"
                              placeholder="e.g., my-survey"
                              value={pushFormData.alias}
                              onChange={(e) => setPushFormData({...pushFormData, alias: e.target.value})}
                            />
                          </div>
                          <div className="form-group">
                            <label>Description (optional)</label>
                            <textarea
                              placeholder="Describe this object..."
                              value={pushFormData.description}
                              onChange={(e) => setPushFormData({...pushFormData, description: e.target.value})}
                              rows={3}
                            />
                          </div>

                          {pushResult && (
                            <div className={`push-result ${pushResult.success ? 'success' : 'error'}`}>
                              {pushResult.message}
                              {pushResult.success && pushResult.data && (
                                <div className="push-details">
                                  <a href={pushResult.data.url} target="_blank" rel="noopener noreferrer">
                                    View on Coop →
                                  </a>
                                </div>
                              )}
                            </div>
                          )}

                          <div className="modal-actions">
                            <button
                              onClick={() => setShowPushModal(false)}
                              className="cancel-button"
                              disabled={pushing}
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handlePushToCoop}
                              className="submit-button"
                              disabled={pushing}
                            >
                              {pushing ? 'Pushing...' : 'Push to Coop'}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <pre className="edsl-object-preview">
                    {JSON.stringify(message.data.result, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="result-text">
                  {message.data.result === null || message.data.result === 'None' ? (
                    <div style={{ color: '#999', fontStyle: 'italic' }}>
                      This formatter displays output in the console/terminal but doesn't return displayable content.
                      Try selecting a different format.
                    </div>
                  ) : typeof message.data.result === 'string' ? (
                    (() => {
                      // Use explicit output_type if specified
                      if (outputType === 'markdown') {
                        return (
                          <div className="markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.data.result}</ReactMarkdown>
                          </div>
                        )
                      }

                      // Otherwise show as plain text
                      return <div style={{ whiteSpace: 'pre-wrap' }}>{message.data.result}</div>
                    })()
                  ) : typeof message.data.result === 'object' ? (
                    (() => {
                      const jsonStr = JSON.stringify(message.data.result, null, 2)
                      const sizeKB = (jsonStr.length / 1024).toFixed(1)
                      return (
                        <>
                          <div style={{ marginBottom: '8px', color: '#666', fontSize: '12px' }}>
                            Result size: {sizeKB} KB
                          </div>
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '12px' }}>
                            {jsonStr.length > 10000 ? jsonStr.substring(0, 10000) + '\n\n... [truncated, result is very large]' : jsonStr}
                          </pre>
                        </>
                      )
                    })()
                  ) : (
                    String(message.data.result)
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  if (message.type === 'error') {
    return (
      <div className="message-container assistant">
        <div className="message-content error-message">
          <strong>Error:</strong> {message.data}
        </div>
      </div>
    )
  }

  return null
}

function AppSearchSelector({ apps, onAppSelect }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  const filteredApps = apps.filter(app => {
    // Handle both structured and string formats
    const name = app.name?.name || app.name || ''
    const description = app.description?.short || app.description?.long || app.description || ''
    return name.toLowerCase().includes(searchTerm.toLowerCase()) ||
           description.toLowerCase().includes(searchTerm.toLowerCase())
  })

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => Math.min(prev + 1, filteredApps.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter' && filteredApps.length > 0) {
      e.preventDefault()
      onAppSelect(filteredApps[selectedIndex])
    }
  }

  useEffect(() => {
    setSelectedIndex(0)
  }, [searchTerm])

  return (
    <div className="app-search-selector">
      <strong>Select an app to get started:</strong>
      <input
        type="text"
        className="app-search-input"
        placeholder="Search apps..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
      <div className="app-search-results">
        {filteredApps.length === 0 ? (
          <div className="no-results">No apps match your search</div>
        ) : (
          filteredApps.map((app, idx) => (
            <div
              key={app.app_id}
              className={`app-search-item ${idx === selectedIndex ? 'selected' : ''}`}
              onClick={() => onAppSelect(app)}
              onMouseEnter={() => setSelectedIndex(idx)}
            >
              <div className="app-search-name">{app.name?.name || app.name}</div>
              <div className="app-search-desc">{app.description?.short || app.description || 'No description'}</div>
            </div>
          ))
        )}
      </div>
      {filteredApps.length > 0 && (
        <div className="search-hint">
          Press Enter to use "{filteredApps[selectedIndex].name?.name || filteredApps[selectedIndex].name}" or click to select
        </div>
      )}
    </div>
  )
}

function EdslObjectSelector({ param, value, onChange }) {
  const [objects, setObjects] = useState([])
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [previewObject, setPreviewObject] = useState(null)

  useEffect(() => {
    const fetchObjects = async () => {
      setLoading(true)
      try {
        const response = await fetch(`/api/edsl-objects/${param.expected_object_type || 'ScenarioList'}`)
        if (response.ok) {
          const data = await response.json()
          setObjects(data.objects || [])
        }
      } catch (err) {
        console.error('Failed to fetch EDSL objects:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchObjects()
  }, [param.expected_object_type])

  const filteredObjects = objects.filter(obj =>
    (obj.alias && obj.alias.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (obj.description && obj.description.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const selectedObject = objects.find(obj => obj.uuid === value)

  const handleSelect = (obj) => {
    onChange(param.question_name, obj.uuid)
    setIsOpen(false)
    setSearchTerm('')
  }

  const handlePreview = (obj, e) => {
    e.stopPropagation()
    setPreviewObject(previewObject?.uuid === obj.uuid ? null : obj)
  }

  return (
    <div className="form-group-inline">
      <label>{param.question_text}</label>
      {loading ? (
        <div className="edsl-loading">Loading {param.expected_object_type} from Coop...</div>
      ) : (
        <div className="edsl-object-dropdown">
          <button
            type="button"
            className="edsl-dropdown-button"
            onClick={() => setIsOpen(!isOpen)}
          >
            <span className="dropdown-value">
              {selectedObject ? (
                <>
                  <span className="edsl-badge">{param.expected_object_type}</span>
                  {selectedObject.alias || selectedObject.uuid.substring(0, 8)}
                </>
              ) : (
                `Select ${param.expected_object_type}...`
              )}
            </span>
            <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
          </button>

          {isOpen && (
            <div className="edsl-dropdown-panel">
              <input
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="edsl-dropdown-search"
                autoFocus
              />
              <div className="edsl-dropdown-list">
                {filteredObjects.length === 0 ? (
                  <div className="edsl-dropdown-empty">No {param.expected_object_type} found</div>
                ) : (
                  filteredObjects.map(obj => (
                    <div key={obj.uuid}>
                      <div
                        className={`edsl-dropdown-item ${value === obj.uuid ? 'selected' : ''}`}
                        onClick={() => handleSelect(obj)}
                      >
                        <div className="dropdown-item-main">
                          <div className="dropdown-item-header">
                            <span className="dropdown-alias">{obj.alias || obj.uuid.substring(0, 12)}</span>
                            <button
                              className="preview-icon"
                              onClick={(e) => handlePreview(obj, e)}
                              title="View details"
                              type="button"
                            >
                              👁️
                            </button>
                          </div>
                          {obj.description && <div className="dropdown-description">{obj.description}</div>}
                          <div className="dropdown-meta">
                            <span className="dropdown-owner">@{obj.owner_username}</span>
                            {obj.url && <span className="dropdown-uuid">UUID: {obj.uuid.substring(0, 8)}...</span>}
                          </div>
                        </div>
                      </div>
                      {previewObject?.uuid === obj.uuid && (
                        <div className="edsl-object-preview">
                          <div className="preview-label">Details:</div>
                          <div className="preview-field"><strong>UUID:</strong> {obj.uuid}</div>
                          <div className="preview-field"><strong>Alias:</strong> {obj.alias}</div>
                          {obj.description && <div className="preview-field"><strong>Description:</strong> {obj.description}</div>}
                          <div className="preview-field"><strong>Owner:</strong> @{obj.owner_username}</div>
                          {obj.url && (
                            <div className="preview-field">
                              <a href={obj.url} target="_blank" rel="noopener noreferrer" className="preview-link">
                                View on Coop →
                              </a>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {selectedObject && !isOpen && (
            <div className="selected-object-summary">
              <div className="summary-row">
                <span className="summary-label">Selected:</span>
                <span className="summary-value">{selectedObject.alias}</span>
              </div>
              {selectedObject.description && (
                <div className="summary-description">{selectedObject.description}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function InputForm({ app, onSubmit }) {
  const [formData, setFormData] = useState({})
  const [uploading, setUploading] = useState(false)

  const handleInputChange = (questionName, value) => {
    setFormData(prev => ({ ...prev, [questionName]: value }))
  }

  const handleCheckboxChange = (questionName, option, checked) => {
    setFormData(prev => {
      const current = prev[questionName] || []
      if (checked) {
        return { ...prev, [questionName]: [...current, option] }
      } else {
        return { ...prev, [questionName]: current.filter(o => o !== option) }
      }
    })
  }

  const handleFileUpload = async (questionName, file) => {
    if (!file) return

    setUploading(true)
    try {
      const formDataUpload = new FormData()
      formDataUpload.append('file', file)

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formDataUpload
      })

      if (!response.ok) throw new Error('File upload failed')

      const result = await response.json()

      // Store the server-side file path
      setFormData(prev => ({ ...prev, [questionName]: result.file_path }))
    } catch (err) {
      alert('File upload failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(app, formData)
  }

  const renderFormField = (param) => {
    const { question_name, question_text, question_type, question_options } = param

    switch (question_type) {
      case 'edsl_object':
        return <EdslObjectSelector key={question_name} param={param} value={formData[question_name]} onChange={handleInputChange} />

      case 'free_text':
        return (
          <div key={question_name} className="form-group-inline">
            <label>{question_text}</label>
            <textarea
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
            />
          </div>
        )

      case 'numerical':
        return (
          <div key={question_name} className="form-group-inline">
            <label>{question_text}</label>
            <input
              type="number"
              placeholder="Enter a number"
              value={formData[question_name] ?? ''}
              onChange={(e) => handleInputChange(question_name, e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>
        )

      case 'multiple_choice':
        if (question_options && question_options.length > 0) {
          return (
            <div key={question_name} className="form-group-inline">
              <label>{question_text}</label>
              <select
                value={formData[question_name] || ''}
                onChange={(e) => handleInputChange(question_name, e.target.value)}
              >
                <option value="">Select an option...</option>
                {question_options.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>
          )
        }
        return (
          <div key={question_name} className="form-group-inline">
            <label>{question_text}</label>
            <input
              type="text"
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
            />
          </div>
        )

      case 'checkbox':
        if (question_options && question_options.length > 0) {
          return (
            <div key={question_name} className="form-group-inline">
              <label>{question_text}</label>
              <div className="checkbox-group">
                {question_options.map(option => (
                  <label key={option}>
                    <input
                      type="checkbox"
                      checked={(formData[question_name] || []).includes(option)}
                      onChange={(e) => handleCheckboxChange(question_name, option, e.target.checked)}
                    />
                    {option}
                  </label>
                ))}
              </div>
            </div>
          )
        }
        return (
          <div key={question_name} className="form-group-inline">
            <label>{question_text}</label>
            <input
              type="text"
              value={Array.isArray(formData[question_name]) ? formData[question_name].join(', ') : ''}
              onChange={(e) => handleInputChange(question_name, e.target.value.split(',').map(s => s.trim()))}
            />
          </div>
        )

      case 'file_upload':
        return (
          <div key={question_name} className="form-group-inline">
            <label>{question_text}</label>
            <div className="file-upload-container">
              <input
                type="file"
                id={`file-${question_name}`}
                className="file-input"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleFileUpload(question_name, file)
                }}
                disabled={uploading}
              />
              <label htmlFor={`file-${question_name}`} className="file-upload-button">
                {uploading ? 'Uploading...' : formData[question_name] ? 'Change File' : 'Choose File'}
              </label>
              {formData[question_name] && (
                <span className="file-upload-name">
                  File uploaded ✓
                </span>
              )}
            </div>
          </div>
        )

      default:
        return (
          <div key={question_name} className="form-group-inline">
            <label>{question_text}</label>
            <input
              type="text"
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
            />
          </div>
        )
    }
  }

  return (
    <form onSubmit={handleSubmit} className="input-form">
      {app.parameters && app.parameters.map(param => renderFormField(param))}
      <button type="submit" className="submit-button-inline" disabled={uploading}>
        {uploading ? 'Uploading files...' : 'Run'}
      </button>
    </form>
  )
}

function OldAppDetail({ app, onBack, apiBase }) {
  const [formData, setFormData] = useState({})
  const [messages, setMessages] = useState([]) // Chat-like message history
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState(null)
  const [isLocked, setIsLocked] = useState(false)

  const handleInputChange = (questionName, value) => {
    setFormData(prev => ({ ...prev, [questionName]: value }))
  }

  const handleCheckboxChange = (questionName, option, checked) => {
    setFormData(prev => {
      const current = prev[questionName] || []
      if (checked) {
        return { ...prev, [questionName]: [...current, option] }
      } else {
        return { ...prev, [questionName]: current.filter(o => o !== option) }
      }
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setExecuting(true)
    setError(null)
    setIsLocked(true)

    // Add user submission as a message
    const submissionMessage = {
      type: 'submission',
      data: { ...formData },
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, submissionMessage])

    try {
      const response = await fetch(`${apiBase}/apps/${app.app_id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: formData })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Execution failed')
      }

      const result = await response.json()

      if (result.status === 'failed') {
        setError(result.error || 'Execution failed')
        setMessages(prev => [...prev, {
          type: 'error',
          data: result.error,
          timestamp: new Date().toISOString()
        }])
      } else {
        // Add result as a message with formatter options
        setMessages(prev => [...prev, {
          type: 'result',
          data: result,
          timestamp: new Date().toISOString(),
          selectedFormatter: null
        }])
      }
    } catch (err) {
      setError(err.message)
      setMessages(prev => [...prev, {
        type: 'error',
        data: err.message,
        timestamp: new Date().toISOString()
      }])
    } finally {
      setExecuting(false)
    }
  }

  const handleRunAgain = () => {
    setFormData({})
    setIsLocked(false)
  }

  const handleFormatterSelect = async (messageIndex, formatterName, originalAnswers) => {
    setExecuting(true)
    setError(null)

    try {
      const response = await fetch(`${apiBase}/apps/${app.app_id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: originalAnswers,
          formatter_name: formatterName
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Execution failed')
      }

      const result = await response.json()

      if (result.status === 'failed') {
        setError(result.error || 'Execution failed')
      } else {
        // Update the message with the formatted result
        setMessages(prev => prev.map((msg, idx) =>
          idx === messageIndex ? { ...msg, data: result, selectedFormatter: formatterName } : msg
        ))
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setExecuting(false)
    }
  }

  const renderFormField = (param) => {
    const { question_name, question_text, question_type, question_options } = param

    switch (question_type) {
      case 'free_text':
        return (
          <div key={question_name} className="form-group">
            <label>{question_text}</label>
            <textarea
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
            />
          </div>
        )

      case 'numerical':
        return (
          <div key={question_name} className="form-group">
            <label>{question_text}</label>
            <input
              type="number"
              placeholder="Enter a number (e.g., 0.05, 100, 3.14)"
              step="any"
              value={formData[question_name] ?? ''}
              onChange={(e) => handleInputChange(question_name, e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>
        )

      case 'multiple_choice':
        if (question_options && question_options.length > 0) {
          return (
            <div key={question_name} className="form-group">
              <label>{question_text}</label>
              <select
                value={formData[question_name] || ''}
                onChange={(e) => handleInputChange(question_name, e.target.value)}
              >
                <option value="">Select an option...</option>
                {question_options.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>
          )
        }
        return (
          <div key={question_name} className="form-group">
            <label>{question_text}</label>
            <input
              type="text"
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
              placeholder="Enter your choice"
            />
          </div>
        )

      case 'checkbox':
        if (question_options && question_options.length > 0) {
          return (
            <div key={question_name} className="form-group">
              <label>{question_text}</label>
              <div className="checkbox-group">
                {question_options.map(option => (
                  <label key={option}>
                    <input
                      type="checkbox"
                      checked={(formData[question_name] || []).includes(option)}
                      onChange={(e) => handleCheckboxChange(question_name, option, e.target.checked)}
                    />
                    {option}
                  </label>
                ))}
              </div>
            </div>
          )
        }
        return (
          <div key={question_name} className="form-group">
            <label>{question_text}</label>
            <input
              type="text"
              value={Array.isArray(formData[question_name]) ? formData[question_name].join(', ') : ''}
              onChange={(e) => handleInputChange(question_name, e.target.value.split(',').map(s => s.trim()))}
              placeholder="Enter comma-separated values"
            />
          </div>
        )

      case 'yes_no':
        const yesNoOptions = question_options || ['Yes', 'No']
        return (
          <div key={question_name} className="form-group">
            <label>{question_text}</label>
            <select
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
            >
              <option value="">Select...</option>
              {yesNoOptions.map(option => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
        )

      default:
        return (
          <div key={question_name} className="form-group">
            <label>{question_text}</label>
            <input
              type="text"
              value={formData[question_name] || ''}
              onChange={(e) => handleInputChange(question_name, e.target.value)}
            />
          </div>
        )
    }
  }

  return (
    <div className="container">
      <button onClick={onBack} className="back-button">← Back to Apps</button>

      <div className="app-detail">
        <h1>{app.name?.name || app.name}</h1>
        <p style={{ color: '#666', marginBottom: '20px' }}>{app.description?.long || app.description?.short || app.description}</p>

        {error && <div className="error">{error}</div>}

        {/* Chat-like message feed */}
        <div className="chat-container">
          {messages.map((message, idx) => (
            <div key={idx} className="chat-message">
              {message.type === 'submission' && (
                <div className="message-submission">
                  <strong>Your Input:</strong>
                  <div className="submission-summary">
                    {Object.entries(message.data).map(([key, value]) => (
                      <div key={key} className="param-summary">
                        <span className="param-key">{key}:</span>{' '}
                        <span className="param-value">
                          {Array.isArray(value) ? value.join(', ') : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {message.type === 'result' && (
                <div className="message-result">
                  <div className="formatter-selection-inline">
                    <strong>Select Format:</strong>
                    <div className="formatter-buttons">
                      {app.available_formatters.map(formatter => (
                        <button
                          key={formatter}
                          onClick={() => {
                            const submissionIdx = messages.findIndex((m, i) => i < idx && m.type === 'submission')
                            const originalAnswers = submissionIdx >= 0 ? messages[submissionIdx].data : formData
                            handleFormatterSelect(idx, formatter, originalAnswers)
                          }}
                          className="formatter-button"
                          disabled={executing}
                        >
                          {formatter}
                          {message.selectedFormatter === formatter && ' ✓'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {message.data.result && (
                    <div className="result-container">
                      <strong>Result:</strong>
                      <div className="result-content">
                        {typeof message.data.result === 'string'
                          ? message.data.result
                          : JSON.stringify(message.data.result, null, 2)}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {message.type === 'error' && (
                <div className="message-error">
                  <strong>Error:</strong> {message.data}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Form - locked after submission */}
        <form onSubmit={handleSubmit} className={isLocked ? 'form-locked' : ''}>
          <h2>{isLocked ? 'Previous Input' : 'Input Parameters'}</h2>
          {app.parameters && app.parameters.map(param => renderFormField(param))}

          <div className="form-actions">
            {!isLocked ? (
              <button type="submit" className="submit-button" disabled={executing}>
                {executing ? 'Running...' : 'Submit'}
              </button>
            ) : (
              <button type="button" onClick={handleRunAgain} className="submit-button">
                Run Again
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}

export default App
