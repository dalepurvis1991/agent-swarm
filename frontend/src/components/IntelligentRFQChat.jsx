import { useState } from 'react'

function IntelligentRFQChat() {
  const [messages, setMessages] = useState([])
  const [currentInput, setCurrentInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState('ready') // ready, needs_clarification, ready_to_send
  const [suppliers, setSuppliers] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [emailsGenerated, setEmailsGenerated] = useState([])

  const processRFQ = async (specification) => {
    setIsLoading(true)
    try {
      const response = await fetch('http://localhost:8000/intelligent-rfq/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ specification })
      })

      if (!response.ok) {
        throw new Error('Failed to process RFQ')
      }

      const data = await response.json()
      
      setMessages(prev => [
        ...prev,
        { role: 'user', content: specification },
        { role: 'assistant', content: data.message }
      ])

      setStatus(data.status)
      setAnalysis(data.analysis)

      if (data.status === 'needs_clarification') {
        setMessages(prev => [
          ...prev,
          { role: 'assistant', content: data.question }
        ])
      } else if (data.status === 'ready_to_send') {
        setSuppliers(data.emails_generated || [])
        setEmailsGenerated(data.emails_generated || [])
        
        // Show success message with supplier count
        const successMessage = `🎉 Success! I found ${data.suppliers_found} suppliers and generated custom emails for each one. Here's what I found:`
        setMessages(prev => [
          ...prev,
          { role: 'assistant', content: successMessage }
        ])
      }

    } catch (error) {
      console.error('Error processing RFQ:', error)
      setMessages(prev => [
        ...prev,
        { role: 'user', content: specification },
        { role: 'assistant', content: 'Sorry, there was an error processing your request. Please make sure the backend is running and try again.' }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const clarifyRFQ = async (clarification) => {
    setIsLoading(true)
    try {
      const response = await fetch('http://localhost:8000/intelligent-rfq/clarify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ specification: clarification })
      })

      if (!response.ok) {
        throw new Error('Failed to process clarification')
      }

      const data = await response.json()
      
      setMessages(prev => [
        ...prev,
        { role: 'user', content: clarification },
        { role: 'assistant', content: data.message }
      ])

      setStatus(data.status)
      setAnalysis(data.analysis)

      if (data.status === 'needs_clarification') {
        setMessages(prev => [
          ...prev,
          { role: 'assistant', content: data.question }
        ])
      } else if (data.status === 'ready_to_send') {
        setSuppliers(data.emails_generated || [])
        setEmailsGenerated(data.emails_generated || [])
        
        const successMessage = `🎉 Perfect! I found ${data.suppliers_found} suppliers and generated custom emails for each one.`
        setMessages(prev => [
          ...prev,
          { role: 'assistant', content: successMessage }
        ])
      }

    } catch (error) {
      console.error('Error processing clarification:', error)
      setMessages(prev => [
        ...prev,
        { role: 'user', content: clarification },
        { role: 'assistant', content: 'Sorry, there was an error processing your clarification. Please try again.' }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!currentInput.trim() || isLoading) return

    if (status === 'ready') {
      processRFQ(currentInput.trim())
    } else if (status === 'needs_clarification') {
      clarifyRFQ(currentInput.trim())
    }
    
    setCurrentInput('')
  }

  const reset = () => {
    setMessages([])
    setCurrentInput('')
    setIsLoading(false)
    setStatus('ready')
    setSuppliers([])
    setAnalysis(null)
    setEmailsGenerated([])
  }

  return (
    <div className="max-w-6xl mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-blue-600 text-white p-4">
        <h2 className="text-xl font-semibold">🤖 Intelligent RFQ Assistant</h2>
        <p className="text-blue-100 text-sm">
          Tell me what you need, and I'll search the web to find the best suppliers and create custom emails for each one
        </p>
      </div>

      {/* Chat Messages */}
      <div className="h-96 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <div className="mb-4">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <p className="text-lg">What do you need quotes for?</p>
            <div className="mt-4 text-sm space-y-2">
              <p><strong>Examples:</strong></p>
              <div className="bg-blue-50 p-3 rounded-lg text-left max-w-md mx-auto">
                <p>• "I need some paint for a warehouse floor"</p>
                <p>• "Insurance for my delivery van"</p>
                <p>• "Steel RSJ beams for construction"</p>
                <p>• "Commercial flooring for an office"</p>
              </div>
            </div>
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
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 text-gray-800 max-w-xs lg:max-w-md px-4 py-2 rounded-lg">
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span className="text-sm">
                  {status === 'ready' ? 'Analyzing your request and searching for suppliers...' : 'Processing your clarification...'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Analysis Display */}
      {analysis && (
        <div className="border-t border-gray-200 p-4 bg-blue-50">
          <h3 className="text-lg font-semibold text-blue-800 mb-2">📊 Analysis</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <strong>Industry:</strong> {analysis.industry}
            </div>
            <div>
              <strong>Product Category:</strong> {analysis.product_category}
            </div>
            <div>
              <strong>Complexity:</strong> {analysis.estimated_complexity}
            </div>
            <div>
              <strong>Description:</strong> {analysis.product_description}
            </div>
          </div>
        </div>
      )}

      {/* Suppliers Found */}
      {status === 'ready_to_send' && emailsGenerated.length > 0 && (
        <div className="border-t border-gray-200 p-4 bg-green-50">
          <h3 className="text-lg font-semibold text-green-800 mb-4">✅ Suppliers Found & Emails Generated</h3>
          <div className="space-y-4">
            {emailsGenerated.map((supplier, index) => (
              <div key={index} className="bg-white p-4 rounded-lg border border-green-200">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-semibold text-gray-900">{supplier.supplier}</h4>
                  {supplier.estimated_price && (
                    <span className="text-green-600 font-semibold">
                      ~£{supplier.estimated_price}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mb-2">
                  <strong>Website:</strong> {supplier.website}
                </p>
                <details className="text-sm">
                  <summary className="cursor-pointer text-blue-600 hover:text-blue-800">
                    View Custom Email →
                  </summary>
                  <div className="mt-2 p-3 bg-gray-50 rounded border text-gray-700 whitespace-pre-wrap">
                    {supplier.email_content}
                  </div>
                </details>
              </div>
            ))}
          </div>
          
          <div className="mt-4 text-center">
            <button
              onClick={() => alert('Email sending functionality would be implemented here')}
              className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition-colors"
            >
              Send All Emails
            </button>
          </div>
        </div>
      )}

      {/* Input Form */}
      <div className="border-t border-gray-200 p-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            placeholder={
              status === 'ready' 
                ? "Describe what you need (e.g., 'I need some paint for a warehouse floor')"
                : "Please provide the additional information requested above..."
            }
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !currentInput.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Processing...' : status === 'ready' ? 'Start' : 'Send'}
          </button>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={reset}
              className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              Reset
            </button>
          )}
        </form>
      </div>
    </div>
  )
}

export default IntelligentRFQChat 