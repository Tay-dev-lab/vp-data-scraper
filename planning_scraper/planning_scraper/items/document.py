"""
Document Item - represents a PDF document associated with a planning application.

Only documents that pass the drawing pattern filter will be downloaded and stored.
"""

import scrapy
from itemloaders.processors import TakeFirst, MapCompose

from ..utils.text_cleaner import clean_text


class DocumentItem(scrapy.Item):
    """
    Scrapy Item for a planning document (PDF).

    Only documents matching drawing patterns (plans, elevations, etc.)
    will be processed through the full pipeline.
    """

    # Source information
    document_url = scrapy.Field(output_processor=TakeFirst())
    source_url = scrapy.Field(output_processor=TakeFirst())  # URL where document was found
    filename = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )

    # Parent application reference
    application_reference = scrapy.Field(output_processor=TakeFirst())
    council_name = scrapy.Field(output_processor=TakeFirst())

    # Document classification (set by DocumentFilterPipeline)
    document_type = scrapy.Field(output_processor=TakeFirst())  # floor_plan, elevation, etc.
    matches_pattern = scrapy.Field()  # Boolean - passed drawing filter
    matched_patterns = scrapy.Field()  # List of patterns that matched

    # Download state (set by PDFDownloadPipeline)
    local_path = scrapy.Field()  # Temp file path after download
    download_status = scrapy.Field()  # 'pending', 'success', 'failed'
    download_error = scrapy.Field()  # Error message if failed
    content_type = scrapy.Field()  # MIME type from response
    file_size = scrapy.Field()  # Size in bytes

    # Compression state (set by PDFCompressPipeline)
    compressed = scrapy.Field()  # Boolean - was compressed
    original_size = scrapy.Field()  # Size before compression
    compressed_size = scrapy.Field()  # Size after compression

    # S3 state (set by S3UploadPipeline)
    s3_bucket = scrapy.Field()
    s3_key = scrapy.Field()
    s3_url = scrapy.Field()  # Full S3 URL
    upload_status = scrapy.Field()  # 'pending', 'success', 'failed'
    upload_error = scrapy.Field()

    # Supabase state (set by SupabasePipeline)
    _application_id = scrapy.Field()  # Supabase UUID of parent application
    _document_id = scrapy.Field()  # Supabase UUID of this document record

    # Internal tracking
    _portal_framework = scrapy.Field()
    _scraped_at = scrapy.Field()
