import curl_cffi
from datetime import datetime
import os
from dotenv import load_dotenv

# Determine environment
env = os.environ.get("PYTHON_ENV", "development")

# Load the appropriate .env file
load_dotenv(f".env.{env}")

# Create directories for outputs if they don't exist
os.makedirs('reports', exist_ok=True)
os.makedirs('results', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Get current timestamp for filenames
def get_timestamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')

# Get log filename with spider name and timestamp
def get_log_filename(spider):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"logs/{spider.name}_log_{timestamp}.log"

# Scrapy settings for base project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "app"

SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 16

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 2
# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 8
CONCURRENT_REQUESTS_PER_IP = 16
RANDOMIZE_DOWNLOAD_DELAY = True

# Disable cookies (enabled by default)
COOKIES_ENABLED = True
COOKIES_DEBUG = True
# Redirect settings
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 5  # Maximum number of redirects to follow
REDIRECT_PRIORITY_ADJUST = +2  # Adjust priority of redirected requests
# Additional helpful settings
HTTPERROR_ALLOWED_CODES = [301, 302, 303, 307, 308, 202]  # Allow these HTTP codes


# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
# }

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#     'middlewares.DynamicDomainMiddleware': 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    'middlewares.CustomProxyMiddleware': 50,  # Lower number = earlier execution
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': 600,
    'middlewares.CouncilNameMiddleware': 120
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
EXTENSIONS = {
    #'scrapy.extensions.feedexport.FeedExporter': None,  # Disable default to use our custom one
    'extensions.PlanningStatsSummaryExtension': 100,  # Our custom extension
    'extensions.LogFileExtension': 200,  # Custom extension for log files
    'extensions.StatusCodeAnalyzerExtension': 500,
    'extensions.ItemFeedExporterExtension': 50,  # Add our new extension with high priority
}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "app.app.pipelines.data_transformation.DataTransformationPipeline": 310,
    "app.app.pipelines.validation.ValidationPipeline": 700,
    "app.app.pipelines.database_upload.DatabasePipeline": 720,
}

# Pipeline-specific settings
BATCH_SIZE = 100
REJECTED_ITEMS_PATH = 'data/rejected_items.jsonl'
FAILED_DB_BATCHES_PATH = 'data/failed_db_batches.jsonl'

# Database settings
DB_USER = os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")
DB_NAME = os.environ.get("POSTGRES_DB")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = True
# The initial download delay
AUTOTHROTTLE_START_DELAY = 3
# The maximum download delay to be set in case of high latencies
AUTOTHROTTLE_MAX_DELAY = 30
# The average number of requests Scrapy should be sending in parallel to
# each remote server
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
# Enable showing throttling stats for every response received:
AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

DOWNLOAD_HANDLERS = {
    "http": "scrapy_impersonate.ImpersonateDownloadHandler",
    "https": "scrapy_impersonate.ImpersonateDownloadHandler",
}

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 0  # No retries for 202s - just accept and move on
RETRY_HTTP_CODES = [500, 502, 503, 504, 400, 403, 404, 408]  # Remove 202 from retry codes
RETRY_DELAY = 5



# Add these settings
RETRY_PRIORITY_ADJUST = -1  # Lower priority for retries
DOWNLOAD_TIMEOUT = 180  # 3 minutes timeout for downloads

# Define the feed_uri_params function before using it in FEEDS
def feed_uri_params(params, spider):
    params['time'] = get_timestamp()
    return params

# Configure FEEDS with proper paths - ensure this is correctly formatted
FEEDS = {
    # Regular output for items - now in results folder
    'results/%(name)s_results_%(time)s.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'indent': 4,
        'item_class': 'items.items.PlanningApplicationItem',  # Fixed to item_class (singular)
    },
    # Original items directly from spider (captured by ItemFeedExporterExtension)
    'results/%(name)s_original_items_%(time)s.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'indent': 4,
        'item_class': 'items.items.PlanningApplicationItem',
    },
    # Summary report with domain statistics
    'reports/planning_summary_%(name)s_%(time)s.json': {
        'format': 'json',
        'encoding': 'utf8',
        'item_class': 'items.items.DomainSummaryItem',  # Fixed to item_class (singular)
        'indent': 4,
    }
}

FEED_URI_PARAMS = feed_uri_params

# Enable stats collection
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'

# Turn off logging of scraped items
LOG_LEVEL = 'DEBUG'  # This will show only INFO and above (hiding DEBUG messages)
# We'll set LOG_FILE dynamically in the LogFileExtension

# Cookie settings
COOKIES_ENABLED = True
COOKIES_DEBUG = True
COOKIES_STRICT_DOMAIN = True  # New in Scrapy 1.8.2


# Remove these as they're not needed with the default middleware
# COOKIES_PERSISTENCE = True
# COOKIES_PERSISTENCE_DIR = 'cookies'