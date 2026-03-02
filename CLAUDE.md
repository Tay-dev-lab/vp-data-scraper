# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VP Data Scraper is a Scrapy-based web scraper that extracts planning applications and PDF documents (planning drawings) from UK council planning portals. It supports multiple portal frameworks (IDOX, ASPX/Northgate) and includes filtering to extract only residential applications and planning drawings.

## Commands

```bash
# Install dependencies
cd planning_scraper
uv sync --dev

# Run IDOX spider (scrapes ~55 UK councils)
uv run scrapy crawl idox -a days_back=30
uv run scrapy crawl idox -a start_date=01/01/2025 -a end_date=31/01/2025

# London boroughs only
uv run scrapy crawl idox -a region=london -a days_back=30

# Single council
uv run scrapy crawl idox -a council=barnet -a days_back=7

# Disable LLM filtering (regex-only, faster)
uv run scrapy crawl idox -a region=london -a days_back=7 -s LLM_FILTER_ENABLED=false

# Run other London spiders
uv run scrapy crawl aspx -a region=london -a days_back=30    # Camden, Merton, Wandsworth
uv run scrapy crawl ocella -a region=london -a days_back=30  # Havering, Hillingdon
uv run scrapy crawl agile -a region=london -a days_back=30   # Islington, Redbridge, Richmond
uv run scrapy crawl atlas -a region=london -a days_back=30   # Kensington & Chelsea

# Run Camden spider (Playwright-based, bypasses filters)
uv run scrapy crawl camden

# Linting and formatting
ruff check planning_scraper/
black planning_scraper/

# Run tests
pytest tests/
```

## Architecture

### Data Flow
```
Spider → ApprovalStatusFilterPipeline → ApplicationFilterPipeline → LLMApplicationFilterPipeline
       → DocumentFilterPipeline → PDFDownloadPipeline → PDFCompressPipeline
       → S3UploadPipeline → SupabasePipeline
```

### Pipeline Priority Order
- **40**: ApprovalStatusFilterPipeline - Drops non-approved applications
- **50**: ApplicationFilterPipeline - Drops non-residential applications
- **75**: LLMApplicationFilterPipeline - LLM classification for new build/conversion (1-30 units)
- **100**: DocumentFilterPipeline - Drops non-drawing documents
- **200**: PDFDownloadPipeline - Downloads PDFs to temp storage
- **300**: PDFCompressPipeline - Compresses PDFs >10MB
- **400**: S3UploadPipeline - Uploads to AWS S3
- **500**: SupabasePipeline - Stores metadata in Supabase

### Key Directories
- `spiders/idox/` - IDOX portal spider (form-based search)
- `spiders/camden/` - Camden ASPX spider (uses Playwright for JS-heavy portal)
- `services/` - Business logic for filtering (application_filter.py, pdf_filter.py)
- `services/llm/` - LLM classification service with providers (OpenAI, Anthropic, Ollama)
- `config/` - Portal URLs (portals.py) and document patterns (patterns.py)
- `pipelines/` - Processing stages

### Item Types
- `PlanningApplicationItem` - Application metadata (reference, address, description, status, dates)
- `DocumentItem` - PDF document metadata (url, filename, type) linked to an application

### Filtering Logic
**Approval Filter** (`pipelines/approval_filter.py`): Regex-based filter that keeps only approved applications. Lenient mode passes items with missing decision field.

**Residential Filter** (`services/application_filter.py`): Includes householder applications, extensions, loft conversions, new builds ≤10 houses or ≤20 apartments. Excludes commercial, industrial, tree works, etc.

**LLM Filter** (`services/llm/classifier.py`): Uses LLM to classify applications as new build or conversion with 1-30 units. Supports OpenAI, Anthropic, and Ollama providers. Includes caching to reduce API costs.

**Drawing Filter** (`services/pdf_filter.py`): High-confidence matches for site plans, floor plans, elevations, sections. Excludes forms, statements, reports, letters.

## Environment Variables

Required in `.env`:
```
S3_BUCKET_NAME=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=eu-west-2
SUPABASE_URL=
SUPABASE_KEY=
PDF_TEMP_DIR=
```

LLM Configuration:
```
LLM_PROVIDER=openai          # openai, anthropic, or ollama
LLM_MODEL=gpt-4o-mini        # Model to use
LLM_API_KEY=sk-...           # OpenAI API key
ANTHROPIC_API_KEY=sk-ant-... # Anthropic API key (if using)
OLLAMA_BASE_URL=http://localhost:11434  # Ollama server URL
```

Optional:
```
PROXY_URL=                    # For proxy support
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
LLM_FILTER_ENABLED=true       # Enable/disable LLM filtering
LLM_FILTER_FALLBACK=permissive  # permissive or strict
APPROVAL_FILTER_ENABLED=true  # Enable/disable approval filter
```

## Adding New Spiders

1. Create directory under `spiders/` (e.g., `spiders/newportal/`)
2. Implement spider inheriting from `scrapy.Spider`
3. Yield `PlanningApplicationItem` and `DocumentItem` objects
4. Add spider module to `SPIDER_MODULES` in settings.py
5. Override filters with `custom_settings` if needed (see CamdenSpider for example)

## Spider Custom Settings

Spiders can override pipeline behavior:
```python
custom_settings = {
    "ITEM_PIPELINES": {
        # Disable application/document filters
        "planning_scraper.pipelines.pdf_download.PDFDownloadPipeline": 200,
        "planning_scraper.pipelines.s3_upload.S3UploadPipeline": 400,
        "planning_scraper.pipelines.supabase.SupabasePipeline": 500,
    },
}
```

## Playwright Setup

For spiders using Playwright (e.g., Camden):
```bash
playwright install chromium
```
