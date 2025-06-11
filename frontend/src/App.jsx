import { useState, useEffect } from 'react'
import QuoteCard from './components/QuoteCard'
import RFQChat from './components/RFQChat'

function App() {
  const [activeTab, setActiveTab] = useState('search')
  const [spec, setSpec] = useState('')
  const [quotes, setQuotes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Check for search parameter in URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const searchParam = urlParams.get('search')
    if (searchParam) {
      setSpec(searchParam)
      setActiveTab('search')
      // Automatically trigger search
      handleSearch(searchParam)
    }
  }, [])

  const handleSearch = async (searchTerm = spec) => {
    if (!searchTerm.trim()) {
      setError('Please enter a specification')
      return
    }

    setLoading(true)
    setError('')
    
    try {
      const response = await fetch(`http://localhost:8000/quotes?spec=${encodeURIComponent(searchTerm)}`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch quotes')
      }
      
      const data = await response.json()
      setQuotes(data)
    } catch (err) {
      setError('Failed to fetch quotes. Please try again.')
      console.error('Error fetching quotes:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Product Quote Dashboard
          </h1>
          <p className="text-gray-600">
            Get quotes for your products with intelligent specification assistance
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="mb-8">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex justify-center space-x-8">
              <button
                onClick={() => setActiveTab('rfq')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'rfq'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                🤖 Smart RFQ Assistant
              </button>
              <button
                onClick={() => setActiveTab('search')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'search'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                🔍 Direct Search
              </button>
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'rfq' && (
          <div className="mb-8">
            <RFQChat />
          </div>
        )}

        {activeTab === 'search' && (
          <>
            {/* Search */}
            <div className="max-w-2xl mx-auto mb-8">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={spec}
                  onChange={(e) => setSpec(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Enter product specification (e.g., eco tote bags)"
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  onClick={() => handleSearch()}
                  disabled={loading}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Searching...' : 'Search'}
                </button>
              </div>
              
              {error && (
                <div className="mt-2 text-red-600 text-sm">
                  {error}
                </div>
              )}
            </div>

            {/* Results */}
            {quotes.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  {quotes.length} Quote{quotes.length !== 1 ? 's' : ''} Found
                </h2>
                
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {quotes.map((quote) => (
                    <QuoteCard key={quote.id} quote={quote} />
                  ))}
                </div>
              </div>
            )}

            {/* No results */}
            {!loading && quotes.length === 0 && spec && (
              <div className="text-center py-12">
                <div className="text-gray-500">
                  <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-lg font-medium text-gray-900 mb-2">No quotes found</p>
                  <p className="text-gray-500">Try searching with different keywords or use the Smart RFQ Assistant</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default App 