# Agent Swarm - Email Processing Backend

[![CI/CD Pipeline](https://github.com/your-username/agent-swarm/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/your-username/agent-swarm/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/poetry-1.6+-blue.svg)](https://python-poetry.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A sophisticated email processing backend system for automated supplier quote requests and response handling. Built with FastAPI, PostgreSQL, and comprehensive testing.

## 🚀 Features

### Core Functionality
- **Automated Supplier Discovery**: Find suppliers using SerpAPI with intelligent filtering
- **RFQ Email Generation**: Professional quote request emails with customizable templates  
- **Real-time Email Processing**: IMAP-based inbox monitoring for supplier responses
- **Quote Parsing**: Extract pricing, lead times, and terms from supplier emails
- **Database Management**: Comprehensive offer storage with PostgreSQL integration

### Development & Operations
- **GitHub Actions CI/CD**: Automated testing, linting, and security scanning
- **Docker Compose**: One-command development environment setup
- **MailHog Integration**: Local email testing and debugging
- **Comprehensive Testing**: 40+ tests covering unit, integration, and email scenarios
- **Code Quality**: Black formatting, Flake8 linting, MyPy type checking, Bandit security

## 📋 Prerequisites

- **Python 3.11+**
- **Poetry 1.6+**
- **Docker & Docker Compose**
- **PostgreSQL 15+** (or use Docker)
- **SerpAPI Key** ([Get free key](https://serpapi.com/))

## 🛠️ Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/your-username/agent-swarm.git
cd agent-swarm

# Install dependencies
poetry install

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment
Edit `.env` with your settings:
```bash
# Required: Get from https://serpapi.com/
SERPAPI_KEY=your_serpapi_key_here

# Database (default works with Docker)
DATABASE_URL=postgresql://dev:dev@localhost:5432/email_processing

# Email settings (MailHog defaults)
SMTP_HOST=localhost
SMTP_PORT=1025
IMAP_HOST=localhost  
IMAP_PORT=1143
```

### 3. Start Services
```bash
# Start PostgreSQL and MailHog
docker-compose up -d

# Run database migrations  
poetry run python -c "
import psycopg
conn = psycopg.connect('postgresql://dev:dev@localhost:5432/email_processing')
for f in ['migrations/001_initial.sql', 'migrations/002_offers.sql']:
    with open(f) as file:
        conn.execute(file.read())
conn.commit()
print('✅ Database ready')
"
```

### 4. Test the System
```bash
# Run comprehensive test suite
poetry run pytest tests/ -v

# Test quote request workflow
poetry run python tools/run_quote.py "eco-friendly tote bags" --k 3 --poll-duration 30
```

## 💻 Usage Examples

### Basic Quote Request
```python
from backend.agents.quote_agent import QuoteAgent
import asyncio

async def request_quotes():
    agent = QuoteAgent()
    results = await agent.process_quotes(
        spec="custom promotional mugs",
        max_suppliers=5,
        poll_duration=60  # seconds
    )
    
    print(f"Found {results['suppliers_found']} suppliers")
    print(f"Sent {results['rfqs_sent']} RFQs")
    print(f"Received {results['offers_received']} offers")

asyncio.run(request_quotes())
```

### Email Parsing
```python
from backend.email.parser import extract_offer

email_content = """
From: supplier@company.com
Subject: Re: RFQ for custom mugs

Thanks for your inquiry. 

Our pricing is $8.50 per unit for quantities over 500.
Lead time is 3-4 weeks from artwork approval.

Best regards,
Sales Team
"""

offer = extract_offer(email_content)
print(f"Price: {offer['currency']}{offer['price']}")
print(f"Lead time: {offer['lead_time']} {offer['lead_time_unit']}")
```

### Offer Management
```python
from backend.app.offers import OfferManager
import asyncio

async def manage_offers():
    # Store a new offer
    offer_data = {
        "price": 15.50,
        "currency": "USD", 
        "lead_time": 14,
        "lead_time_unit": "days"
    }
    
    supplier_info = {"name": "Acme Supplies", "email": "sales@acme.com"}
    
    offer_id = await OfferManager.store_offer(
        offer_data, supplier_info, "promotional items"
    )
    
    # Retrieve offers by specification
    offers = await OfferManager.get_offers_by_spec("promotional items")
    print(f"Found {len(offers)} offers")
    
    # Get statistics
    stats = await OfferManager.get_offer_statistics()
    print(f"Average price: ${stats['avg_price']:.2f}")

asyncio.run(manage_offers())
```

## 🏗️ Architecture

```
agent-swarm/
├── backend/
│   ├── app/
│   │   ├── db.py              # Database connection & config
│   │   └── offers.py          # Offer management & storage
│   ├── agents/
│   │   └── quote_agent.py     # Main orchestration logic
│   ├── email/
│   │   ├── outgoing.py        # SMTP email sending
│   │   └── parser.py          # Email content extraction
│   └── suppliers/
│       ├── serp.py            # SerpAPI integration  
│       └── __init__.py        # Supplier search interface
├── tests/
│   ├── test_*.py              # Comprehensive test suites
│   └── fixtures/              # Test data and mocks
├── tools/
│   └── run_quote.py           # CLI quote tool
├── migrations/
│   ├── 001_initial.sql        # Core database schema
│   └── 002_offers.sql         # Supplier offers table
├── .github/workflows/         # CI/CD automation
├── docker-compose.yml         # Development services
└── pyproject.toml             # Dependencies & config
```

## 🧪 Testing

The project includes comprehensive testing at multiple levels:

```bash
# Run all tests
poetry run pytest tests/ -v

# Unit tests only (fast)
poetry run pytest tests/ -v -m "not integration"

# Integration tests with services
poetry run pytest tests/ -v -m integration

# With coverage report
poetry run pytest tests/ --cov=backend --cov-report=html
```

### Test Categories
- **Email Parsing**: Currency extraction, lead time parsing, Unicode handling
- **Email Sending**: SMTP integration, template validation, error handling  
- **IMAP Processing**: Inbox polling, message filtering, offer extraction
- **Offer Management**: Database operations, validation, statistics
- **Quote Agent**: End-to-end workflow integration
- **Supplier Search**: API integration, result filtering, async operations

## 🔧 Development

### Local Development Commands
```bash
# Install dependencies
poetry install

# Start development services  
docker-compose up -d

# Run database migrations
make db-migrate  # (Linux/macOS)
# or manual: poetry run python -c "..."

# Code formatting
poetry run black .

# Linting
poetry run flake8 backend/ tests/ tools/

# Type checking  
poetry run mypy backend/ tools/ --ignore-missing-imports

# Security scan
poetry run bandit -r backend/
poetry run safety check
```

### Pre-commit Hooks
```bash
# Install pre-commit (optional)
pip install pre-commit
pre-commit install

# Manual run
pre-commit run --all-files
```

## 🐳 Docker Development

The project includes a complete Docker Compose setup:

```yaml
services:
  postgres:   # Database with pgvector extension
  mailhog:    # Email testing (SMTP/Web UI)
```

Access points:
- **MailHog Web UI**: http://localhost:8025
- **PostgreSQL**: localhost:5432 (dev/dev)
- **SMTP**: localhost:1025
- **IMAP**: localhost:1143

## 📊 Monitoring & Debugging

### Email Flow Debugging
1. **MailHog Web UI** (http://localhost:8025): View sent/received emails
2. **Database Queries**: Check `supplier_offers` table for stored offers
3. **Logs**: Comprehensive logging throughout the pipeline

### Common Issues
- **SerpAPI Rate Limits**: Use `SKIP_EXTERNAL_APIS=true` for testing
- **Email Parsing**: Check currency symbols and encoding in test emails
- **IMAP Connection**: Verify MailHog is running on correct ports

## 🤝 Contributing

1. **Fork & Clone**: Create your feature branch
2. **Setup**: Follow quick start guide  
3. **Code**: Follow existing patterns, add tests
4. **Test**: Ensure all tests pass (`make ci-local`)
5. **PR**: Submit with clear description

### Code Standards
- **Black** formatting (88 char line length)
- **Type hints** for public APIs
- **Docstrings** for modules and classes
- **Tests** for new functionality
- **Security** scan with Bandit

## 📈 Performance & Scaling

### Current Capabilities
- **Concurrent Suppliers**: 10+ simultaneous RFQ sending
- **Email Processing**: Real-time IMAP monitoring  
- **Database**: Optimized queries with proper indexing
- **API Rate Limits**: Respectful SerpAPI usage

### Scaling Considerations
- **Celery**: Add for background task processing
- **Redis**: Implement for caching and session management  
- **Load Balancer**: For multiple application instances
- **Database Pooling**: For high-concurrency scenarios

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/agent-swarm/issues)
- **Documentation**: See `/docs` folder for detailed guides
- **Email**: For private inquiries regarding commercial use

---

**Built with ❤️ using FastAPI, PostgreSQL, and modern Python practices.** 