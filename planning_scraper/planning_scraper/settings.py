"""
Scrapy settings for planning_scraper project.

This is the central configuration file for the planning scraper.
Settings can be overridden via environment variables or spider custom_settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# Core Scrapy Settings
# =============================================================================

BOT_NAME = "planning_scraper"

SPIDER_MODULES = ["planning_scraper.spiders.idox"]
NEWSPIDER_MODULE = "planning_scraper.spiders"

# Crawl responsibly by identifying yourself
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Obey robots.txt rules (disable for planning portals that block bots)
ROBOTSTXT_OBEY = False

# =============================================================================
# Concurrency and Throttling
# =============================================================================

# Moderate concurrency to avoid overwhelming servers
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4
CONCURRENT_REQUESTS_PER_IP = 4

# Download delay between requests
DOWNLOAD_DELAY = 1.0

# Enable auto-throttling for adaptive rate limiting
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# Request timeout
DOWNLOAD_TIMEOUT = 60

# =============================================================================
# Cookies and Sessions
# =============================================================================

COOKIES_ENABLED = True
COOKIES_DEBUG = False

# =============================================================================
# Retry Settings
# =============================================================================

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Custom retry settings
HANDLE_202_WAIT = 5.0
HANDLE_202_MAX_RETRIES = 3
RATE_LIMIT_INITIAL_WAIT = 30.0
RATE_LIMIT_MAX_WAIT = 300.0
RATE_LIMIT_MAX_RETRIES = 5

# =============================================================================
# Downloader Middlewares
# =============================================================================

DOWNLOADER_MIDDLEWARES = {
    # Default middlewares (keep enabled)
    "scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware": 300,
    "scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware": 350,
    "scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware": 400,
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": 500,
    # Custom middlewares
    "planning_scraper.middlewares.proxy.ProxyMiddleware": 50,
    "planning_scraper.middlewares.retry.Handle202Middleware": 351,
    "planning_scraper.middlewares.retry.RateLimitMiddleware": 352,
    # Default retry middleware
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 550,
    # Compression middleware
    "scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware": 590,
    # Redirect and cookie middlewares
    "scrapy.downloadermiddlewares.redirect.RedirectMiddleware": 600,
    "scrapy.downloadermiddlewares.cookies.CookiesMiddleware": 700,
    "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750,
}

# =============================================================================
# Item Pipelines
# =============================================================================
# Pipeline priority order:
#   50: Application Filter (residential only)
#  100: Document Filter (drawings only)
#  200: PDF Download
#  300: PDF Compress
#  400: S3 Upload
#  500: Supabase (metadata storage)

ITEM_PIPELINES = {
    "planning_scraper.pipelines.application_filter.ApplicationFilterPipeline": 50,
    "planning_scraper.pipelines.document_filter.DocumentFilterPipeline": 100,
    "planning_scraper.pipelines.pdf_download.PDFDownloadPipeline": 200,
    "planning_scraper.pipelines.pdf_compress.PDFCompressPipeline": 300,
    "planning_scraper.pipelines.s3_upload.S3UploadPipeline": 400,
    "planning_scraper.pipelines.supabase.SupabasePipeline": 500,
}

# =============================================================================
# Proxy Settings
# =============================================================================

PROXY_URL = os.environ.get("PROXY_URL")
PROXY_ENABLED = bool(PROXY_URL)

# =============================================================================
# AWS S3 Settings
# =============================================================================

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

# =============================================================================
# Supabase Settings
# =============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# =============================================================================
# PDF Processing Settings
# =============================================================================

# Temporary directory for PDF downloads
PDF_TEMP_DIR = os.environ.get("PDF_TEMP_DIR")

# PDF compression settings
PDF_COMPRESS_THRESHOLD = 10 * 1024 * 1024  # 10MB
PDF_COMPRESS_DPI = 150

# =============================================================================
# Logging Settings
# =============================================================================

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Stats collection
STATS_DUMP = True

# =============================================================================
# HTTP Cache (optional, for development)
# =============================================================================

# Enable HTTP caching for development (disable in production)
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 3600
# HTTPCACHE_DIR = ".scrapy/httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504]

# =============================================================================
# Memory and Performance
# =============================================================================

# Close spider if memory usage exceeds this limit (0 = disabled)
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 0
MEMUSAGE_WARNING_MB = 500

# Maximum depth to follow
DEPTH_LIMIT = 5

# =============================================================================
# Default Request Headers
# =============================================================================

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# =============================================================================
# Feed Export (for debugging)
# =============================================================================

# Uncomment to enable JSON output for debugging
# FEEDS = {
#     "output/%(name)s_%(time)s.json": {
#         "format": "json",
#         "encoding": "utf-8",
#         "indent": 2,
#     },
# }

# =============================================================================
# Telnet Console (disable in production)
# =============================================================================

TELNETCONSOLE_ENABLED = False

# =============================================================================
# Extensions
# =============================================================================

EXTENSIONS = {
    "scrapy.extensions.telnet.TelnetConsole": None,
    "scrapy.extensions.memusage.MemoryUsage": 100,
    "scrapy.extensions.logstats.LogStats": 100,
    "planning_scraper.extensions.run_logger.RunLoggerExtension": 500,
}

# Run logger settings
RUN_LOG_DIR = "logs/runs"
