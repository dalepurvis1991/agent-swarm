function QuoteCard({ quote }) {
  return (
    <div className="QuoteCard bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow">
      <div className="space-y-4">
        {/* Supplier Name */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {quote.supplier_name || 'Unknown Supplier'}
          </h3>
          {quote.supplier_email && (
            <p className="text-sm text-gray-600">{quote.supplier_email}</p>
          )}
        </div>

        {/* Price */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-500">Price:</span>
          <span className="text-xl font-bold text-green-600">
            {quote.currency || '$'}{quote.price}
          </span>
        </div>

        {/* Lead Time */}
        {quote.lead_time && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-500">Lead Time:</span>
            <span className="text-sm text-gray-900">
              {quote.lead_time} {quote.lead_time_unit || 'days'}
            </span>
          </div>
        )}

        {/* Specification */}
        {quote.spec && (
          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs text-gray-500 truncate" title={quote.spec}>
              {quote.spec}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default QuoteCard 