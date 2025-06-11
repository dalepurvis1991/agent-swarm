import { useState } from 'react'

function RFQChat() {
  const [messages, setMessages] = useState([])
  const [currentInput, setCurrentInput] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [structuredSpec, setStructuredSpec] = useState(null)

  const startRFQSession = async (specification) => {
    setIsLoading(true)
    try {
      const response = await fetch('http://localhost:8000/rfq/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ specification })
      })

      if (!response.ok) {
        throw new Error('Failed to start RFQ session')
      }

      const data = await response.json()
      
      setSessionId(data.session_id)
      setMessages([
        { role: 'user', content: specification },
        ...(data.question ? [{ role: 'assistant', content: data.question }] : [])
      ])

      if (data.status === 'complete') {
        setIsComplete(true)
        setStructuredSpec(data.structured_spec)
      }

    } catch (error) {
      console.error('Error starting RFQ session:', error)
      setMessages([
        { role: 'user', content: specification },
        { role: 'assistant', content: 'Sorry, there was an error processing your request. Please try again.' }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const answerQuestion = async (answer) => {
    if (!sessionId) return

    setIsLoading(true)
    try {
      const response = await fetch('http://localhost:8000/rfq/answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId, answer })
      })

      if (!response.ok) {
        throw new Error('Failed to submit answer')
      }

      const data = await response.json()
      
      const newMessages = [
        ...messages,
        { role: 'user', content: answer },
        ...(data.question ? [{ role: 'assistant', content: data.question }] : [])
      ]
      
      setMessages(newMessages)

      if (data.status === 'complete') {
        setIsComplete(true)
        setStructuredSpec(data.structured_spec)
        if (!data.question) {
          setMessages([
            ...newMessages,
            { role: 'assistant', content: '✅ Perfect! I have all the information needed. Your specification is now complete and ready for quotes.' }
          ])
        }
      }

    } catch (error) {
      console.error('Error submitting answer:', error)
      setMessages([
        ...messages,
        { role: 'user', content: answer },
        { role: 'assistant', content: 'Sorry, there was an error processing your answer. Please try again.' }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!currentInput.trim() || isLoading) return

    if (!sessionId) {
      // Starting a new session
      startRFQSession(currentInput.trim())
    } else {
      // Answering a question
      answerQuestion(currentInput.trim())
    }
    
    setCurrentInput('')
  }

  const handleGetQuotes = () => {
    // Navigate to quotes page with the structured spec
    if (structuredSpec && structuredSpec.product_type) {
      const searchTerm = structuredSpec.product_type
      // For now, just redirect to main page with search
      window.location.href = `/?search=${encodeURIComponent(searchTerm)}`
    }
  }

  const reset = () => {
    setMessages([])
    setCurrentInput('')
    setSessionId(null)
    setIsLoading(false)
    setIsComplete(false)
    setStructuredSpec(null)
  }

  return (
    <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-blue-600 text-white p-4">
        <h2 className="text-xl font-semibold">RFQ Specification Assistant</h2>
        <p className="text-blue-100 text-sm">
          Tell me what you need, and I'll help you refine the details for accurate quotes
        </p>
      </div>

      {/* Chat Messages */}
      <div className="h-96 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <div className="mb-4">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-3.582 8-8 8a8.955 8.955 0 01-4.126-.98L3 20l1.98-5.874A8.955 8.955 0 013 12c0-4.418 3.582-8 8-8s8 3.582 8 8z" />
              </svg>
            </div>
            <p className="text-lg">Start by describing what you need</p>
            <p className="text-sm">Example: "I need eco-friendly tote bags for a corporate event"</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-200 text-gray-800'
              }`}
            >
              <p className="text-sm">{message.content}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 text-gray-800 max-w-xs lg:max-w-md px-4 py-2 rounded-lg">
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Structured Spec Display */}
      {isComplete && structuredSpec && (
        <div className="border-t border-gray-200 p-4 bg-green-50">
          <h3 className="text-lg font-semibold text-green-800 mb-2">✅ Specification Complete</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <strong>Product:</strong> {structuredSpec.product_type}
            </div>
            <div>
              <strong>Quantity:</strong> {structuredSpec.quantity}
            </div>
            <div>
              <strong>Timeline:</strong> {structuredSpec.timeline}
            </div>
            <div>
              <strong>Budget:</strong> {structuredSpec.budget}
            </div>
          </div>
          {structuredSpec.specifications && (
            <div className="mt-2">
              <strong>Specifications:</strong>
              <ul className="list-disc list-inside ml-4 text-sm">
                {Object.entries(structuredSpec.specifications).map(([key, value]) => (
                  <li key={key}>{key}: {value}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Input Form */}
      <div className="border-t border-gray-200 p-4">
        {isComplete ? (
          <div className="flex gap-2">
            <button
              onClick={handleGetQuotes}
              className="flex-1 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
            >
              Get Quotes Now
            </button>
            <button
              onClick={reset}
              className="bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600 transition-colors"
            >
              Start Over
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              placeholder={
                sessionId 
                  ? "Type your answer..." 
                  : "Describe what you need (e.g., eco tote bags for corporate event)"
              }
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !currentInput.trim()}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Sending...' : (sessionId ? 'Answer' : 'Start')}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

export default RFQChat 