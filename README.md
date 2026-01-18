# VP Data Scraper

A Scrapy-based web scraper that extracts planning applications and PDF documents (architectural drawings) from UK council planning portals. The scraper filters for residential applications only and downloads planning drawings (site plans, floor plans, elevations, etc.) to AWS S3, with metadata stored in Supabase.

## Features

- Scrapes 50+ UK council planning portals using IDOX framework
- Filters for residential applications (householder, extensions, loft conversions, small new builds)
- Extracts planning drawings only (site plans, floor plans, elevations, sections)
- Downloads and compresses large PDFs (>10MB)
- Uploads to AWS S3 with organized folder structure
- Stores metadata in Supabase for querying
- Supports proxy rotation and rate limiting
- Browser automation for JavaScript-heavy portals (Playwright)

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Ghostscript (for PDF compression)
- Playwright browsers (for ASPX portals)

### Installation

```bash
cd planning_scraper

# Install dependencies
uv sync --dev

# Install Playwright browsers (if using Camden spider)
playwright install chromium

# Install Ghostscript
# macOS:
brew install ghostscript
# Ubuntu:
sudo apt-get install ghostscript
```

### Configuration

Create a `.env` file in the `planning_scraper/` directory:

```bash
# Required
S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-key
PDF_TEMP_DIR=/tmp/planning-pdfs

# Optional
AWS_REGION=eu-west-2
PROXY_URL=http://user:pass@proxy:port
LOG_LEVEL=INFO
```

### Running the Scraper

```bash
cd planning_scraper

# Scrape all IDOX councils for the last 30 days
scrapy crawl idox -a days_back=30

# Scrape with custom date range (DD/MM/YYYY format)
scrapy crawl idox -a start_date=01/01/2025 -a end_date=31/01/2025

# Run Camden-specific spider (bypasses filters, downloads all documents)
scrapy crawl camden
```

## Architecture

### Data Pipeline

```
┌─────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Spider  │────▶│ Application      │────▶│ Document         │────▶│ PDF Download    │
│         │     │ Filter (50)      │     │ Filter (100)     │     │ Pipeline (200)  │
└─────────┘     │ Residential only │     │ Drawings only    │     │                 │
                └──────────────────┘     └──────────────────┘     └────────┬────────┘
                                                                           │
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     │
│ Supabase        │◀────│ S3 Upload        │◀────│ PDF Compress     │◀────┘
│ Pipeline (500)  │     │ Pipeline (400)   │     │ Pipeline (300)   │
│ Store metadata  │     │ Upload to AWS    │     │ >10MB threshold  │
└─────────────────┘     └──────────────────┘     └──────────────────┘
```

### Directory Structure

```
planning_scraper/
├── planning_scraper/
│   ├── spiders/           # Web scrapers
│   │   ├── idox/          # IDOX portal spider (50+ councils)
│   │   └── camden/        # Camden ASPX spider (Playwright)
│   ├── pipelines/         # Processing stages
│   │   ├── application_filter.py   # Residential filter
│   │   ├── document_filter.py      # Drawing filter
│   │   ├── pdf_download.py         # Download to temp
│   │   ├── pdf_compress.py         # Ghostscript compression
│   │   ├── s3_upload.py            # AWS S3 upload
│   │   └── supabase.py             # Metadata storage
│   ├── services/          # Business logic
│   │   ├── application_filter.py   # Residential detection
│   │   └── pdf_filter.py           # Drawing pattern matching
│   ├── config/            # Configuration
│   │   ├── portals.py     # Portal URLs
│   │   └── patterns.py    # Filter patterns
│   ├── middlewares/       # Request handling
│   │   ├── proxy.py       # Proxy support
│   │   └── retry.py       # Rate limit handling
│   ├── extensions/        # Scrapy extensions
│   │   └── run_logger.py  # Run statistics
│   ├── utils/             # Utilities
│   └── items/             # Data models
├── logs/                  # Run logs (JSON)
├── tests/                 # Test suite
└── pyproject.toml         # Project config
```

## Supported Councils

### IDOX Framework (50+ councils)

The IDOX spider scrapes the following councils:

**planning.* prefix:**
- Fife, Inverclyde, Brentwood

**pa.* prefix:**
- Sevenoaks, Shropshire

**planapp.* prefix:**
- Knowsley

**publicaccess.* prefix:**
- Braintree, Cotswold, Craven, Darlington, Dartford, Dover
- East Hertfordshire, East Lindsey, East Northamptonshire
- Exeter, Forest of Dean, Gloucester, Gosport, Guildford
- Hart, Hastings, Huntingdonshire, Isle of Wight, Kingston
- Maldon, Mendip, Newark & Sherwood, Newcastle-under-Lyme
- Northumberland, Nottingham City, Rushmoor, Rutland
- Solihull, South Ribble, South Somerset, Spelthorne
- St Helens, Stevenage, Stroud, Surrey Heath
- Clackmannanshire, Brentwood

**planningpublicaccess.* prefix:**
- South Downs, Southampton

**Special prefixes:**
- Cairngorms National Park (eplanningcnpa)
- Westminster (idoxpa)
- Tower Hamlets (development)
- Bromley (searchapplications)
- Midlothian (planning-applications)
- Poole (boppa)
- Thurrock (regs)

### Other Frameworks (Future Support)

**Agile Applications (15 councils):**
Cannock, Exmoor, Lake District, Middlesbrough, Mole Valley, New Forest, Rugby, Slough, Snowdonia, Tonbridge & Malling, Pembrokeshire, Flintshire, Islington, Pembrokeshire Coast, Yorkshire Dales

**ASPX/Northgate (6 councils):**
Blackburn, Camden, East Staffordshire, Merton, Tamworth, Wandsworth

**Other:**
- Havering (OCELLA)
- Epping Forest (ARCUS/Salesforce)

## Database Schema

### Supabase Tables

#### `planning_applications`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (auto-generated) |
| `application_reference` | TEXT | Council's reference number (e.g., "2025/0123/FUL") |
| `council_name` | TEXT | Council name (e.g., "fife", "westminster") |
| `site_address` | TEXT | Full site address |
| `postcode` | TEXT | UK postcode |
| `ward` | TEXT | Electoral ward |
| `parish` | TEXT | Parish/town council |
| `application_type` | TEXT | Type (e.g., "Householder", "Full Planning") |
| `proposal` | TEXT | Description of proposed works |
| `status` | TEXT | Current status (e.g., "Decided", "Pending") |
| `decision` | TEXT | Decision if made (e.g., "Granted", "Refused") |
| `registration_date` | DATE | Date application registered |
| `decision_date` | DATE | Date of decision (if decided) |
| `applicant_name` | TEXT | Applicant name |
| `agent_name` | TEXT | Agent/architect name |
| `application_url` | TEXT | URL to application on council portal |
| `project_tag` | TEXT | Project identifier for targeted scrapes |
| `scraped_at` | TIMESTAMP | When data was scraped |

**Unique constraint:** `(council_name, application_reference)`

#### `application_documents`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (auto-generated) |
| `application_id` | UUID | Foreign key to `planning_applications.id` |
| `s3_bucket` | TEXT | S3 bucket name |
| `s3_key` | TEXT | S3 object key/path |
| `document_name` | TEXT | Original filename |
| `document_type` | TEXT | Type (floor_plan, elevation, site_plan, etc.) |
| `file_size_bytes` | INTEGER | File size in bytes |
| `project_tag` | TEXT | Project identifier |

**Unique constraint:** `(s3_bucket, s3_key)`

### S3 Key Structure

Documents are stored with the following key pattern:

```
documents/{council}/{application_ref}/{document_type}/{unique_id}_{filename}.pdf

# Example:
documents/fife/2025_0123_ful/floor_plan/a1b2c3d4_ground-floor-plan.pdf

# With project_tag:
documents/{project_tag}/{council}/{application_ref}/{document_type}/{unique_id}_{filename}.pdf
```

## API Examples

### Query Applications with Documents

```sql
-- Get all applications for a council with their documents
SELECT
    a.application_reference,
    a.site_address,
    a.proposal,
    a.status,
    d.document_name,
    d.document_type,
    d.s3_key
FROM planning_applications a
JOIN application_documents d ON d.application_id = a.id
WHERE a.council_name = 'fife'
ORDER BY a.registration_date DESC;
```

### Supabase JavaScript Client

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Get recent applications with floor plans
const { data, error } = await supabase
  .from('planning_applications')
  .select(`
    application_reference,
    site_address,
    proposal,
    application_documents!inner (
      document_name,
      document_type,
      s3_key
    )
  `)
  .eq('application_documents.document_type', 'floor_plan')
  .order('registration_date', { ascending: false })
  .limit(50)
```

### Supabase Python Client

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get applications by postcode area
result = supabase.table("planning_applications") \
    .select("*, application_documents(*)") \
    .ilike("postcode", "SW1%") \
    .execute()

for app in result.data:
    print(f"{app['application_reference']}: {app['proposal']}")
    for doc in app['application_documents']:
        print(f"  - {doc['document_type']}: {doc['s3_key']}")
```

### Generate S3 Pre-signed URLs

```python
import boto3

s3 = boto3.client('s3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Generate a pre-signed URL valid for 1 hour
url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
    ExpiresIn=3600
)
```

## Deployment Guide

### Local Development

```bash
cd planning_scraper
uv sync --dev

# Run with debug logging
LOG_LEVEL=DEBUG scrapy crawl idox -a days_back=7

# Output items to JSON for debugging
scrapy crawl idox -a days_back=7 -o output.json
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

WORKDIR /app
COPY planning_scraper/ .

RUN uv sync

CMD ["uv", "run", "scrapy", "crawl", "idox", "-a", "days_back=30"]
```

### AWS Lambda Deployment

For serverless deployment, the scraper can be packaged as a Lambda function:

1. **Package dependencies** using a Lambda layer or container image
2. **Configure environment variables** in Lambda configuration
3. **Set up EventBridge** for scheduled execution
4. **Increase timeout** to 15 minutes (Lambda max) for large scrapes

Example Lambda handler:

```python
import subprocess
import os

def handler(event, context):
    days_back = event.get('days_back', 7)

    result = subprocess.run(
        ['scrapy', 'crawl', 'idox', '-a', f'days_back={days_back}'],
        cwd='/var/task/planning_scraper',
        capture_output=True,
        text=True
    )

    return {
        'statusCode': 200 if result.returncode == 0 else 500,
        'body': result.stdout
    }
```

### Scheduled Execution (cron)

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/planning_scraper && uv run scrapy crawl idox -a days_back=1

# Run weekly full scrape
0 3 * * 0 cd /path/to/planning_scraper && uv run scrapy crawl idox -a days_back=7
```

### Production Considerations

1. **Use a proxy service** (e.g., Bright Data, Oxylabs) to avoid IP blocks
2. **Monitor rate limits** - the scraper handles 429 responses with exponential backoff
3. **Set up alerting** on the `logs/runs/` JSON files for failure detection
4. **Configure S3 lifecycle policies** for cost management
5. **Use Supabase Row Level Security** for multi-tenant access

## Troubleshooting

### Common Issues

#### "Ghostscript not found"

PDF compression requires Ghostscript. Install it:

```bash
# macOS
brew install ghostscript

# Ubuntu/Debian
sudo apt-get install ghostscript

# Verify installation
gs --version
```

#### "Playwright browsers not installed"

The Camden spider requires Playwright browsers:

```bash
playwright install chromium
```

#### "403 Forbidden" responses

Some councils block automated access. Solutions:

1. **Enable proxy**: Set `PROXY_URL` in `.env`
2. **Reduce concurrency**: Edit `settings.py` or use spider arguments:
   ```bash
   scrapy crawl idox -s CONCURRENT_REQUESTS=4 -s DOWNLOAD_DELAY=2.0
   ```
3. **Add delays**: The autothrottle will automatically adapt

#### "429 Too Many Requests"

The scraper handles rate limiting automatically with exponential backoff. If persistent:

1. Reduce `CONCURRENT_REQUESTS_PER_DOMAIN` in `settings.py`
2. Increase `RATE_LIMIT_INITIAL_WAIT` (default: 30s)
3. Use a proxy with session rotation

#### "Connection reset" or timeout errors

```bash
# Increase timeout
scrapy crawl idox -s DOWNLOAD_TIMEOUT=120

# Enable retry for more status codes
scrapy crawl idox -s RETRY_HTTP_CODES=[500,502,503,504,408,429,520,521,522]
```

#### "Supabase connection failed"

1. Verify `SUPABASE_URL` and `SUPABASE_KEY` are correct
2. Ensure the service key has write permissions
3. Check tables exist with correct schema:
   ```sql
   SELECT * FROM planning_applications LIMIT 1;
   SELECT * FROM application_documents LIMIT 1;
   ```

#### "S3 upload failed"

1. Verify AWS credentials have `s3:PutObject` permission
2. Check bucket exists and region is correct
3. Test manually:
   ```bash
   aws s3 ls s3://your-bucket-name/
   ```

### Debug Mode

Enable verbose logging:

```bash
LOG_LEVEL=DEBUG scrapy crawl idox -a days_back=1
```

Check run logs:

```bash
ls -la logs/runs/
cat logs/runs/run_*.json | jq '.failures'
```

### Pipeline Bypass

To download all documents without filtering (like Camden spider):

```python
# In your spider
custom_settings = {
    "ITEM_PIPELINES": {
        "planning_scraper.pipelines.pdf_download.PDFDownloadPipeline": 200,
        "planning_scraper.pipelines.pdf_compress.PDFCompressPipeline": 300,
        "planning_scraper.pipelines.s3_upload.S3UploadPipeline": 400,
        "planning_scraper.pipelines.supabase.SupabasePipeline": 500,
    },
}
```

## Development

### Running Tests

```bash
cd planning_scraper
pytest tests/ -v
```

### Code Formatting

```bash
# Format code
black planning_scraper/

# Lint
ruff check planning_scraper/
ruff check planning_scraper/ --fix  # Auto-fix
```

### Adding a New Spider

1. Create a new directory under `spiders/`
2. Implement spider class inheriting from `scrapy.Spider`
3. Yield `PlanningApplicationItem` and `DocumentItem` objects
4. Add spider module to `SPIDER_MODULES` in `settings.py`
5. Test with a small date range:
   ```bash
   scrapy crawl newspider -a days_back=1
   ```

## License

MIT
