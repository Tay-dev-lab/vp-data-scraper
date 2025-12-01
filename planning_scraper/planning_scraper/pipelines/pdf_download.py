"""
PDF Download Pipeline - downloads matching PDF documents.

This pipeline runs after DocumentFilterPipeline (priority 200).
Downloads PDFs to temporary storage for compression and S3 upload.

Uses Scrapy's downloader to maintain session cookies.
"""

import logging
import tempfile
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from scrapy import Request
from scrapy.http import Response
from scrapy.exceptions import DropItem
from twisted.internet import defer

from ..items.document import DocumentItem
from ..utils.text_cleaner import clean_filename


class PDFDownloadPipeline:
    """
    Pipeline that downloads PDF documents to temporary storage.

    Uses Scrapy's downloader to maintain cookies and session state.
    """

    # Maximum file size to download (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    # Valid content types for PDFs
    VALID_CONTENT_TYPES = [
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
        "binary/octet-stream",
    ]

    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir
        self.logger = logging.getLogger(__name__)
        self.crawler = None
        self.stats = {
            "total_downloads": 0,
            "successful": 0,
            "failed": 0,
            "total_bytes": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        temp_dir = crawler.settings.get("PDF_TEMP_DIR")
        pipeline = cls(temp_dir=temp_dir)
        pipeline.crawler = crawler
        return pipeline

    def open_spider(self, spider):
        """Create temp directory when spider opens."""
        if self.temp_dir:
            os.makedirs(self.temp_dir, exist_ok=True)
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="planning_pdfs_")
        self.logger.info(f"PDF temp directory: {self.temp_dir}")

    @defer.inlineCallbacks
    def process_item(self, item, spider):
        """
        Download a PDF document using Scrapy's downloader.

        Only processes DocumentItems that passed the filter.
        """
        # Only process DocumentItems
        if not isinstance(item, DocumentItem):
            return item

        # Only process items that passed the document filter
        if not item.get("matches_pattern"):
            return item

        self.stats["total_downloads"] += 1

        document_url = item.get("document_url")
        if not document_url:
            item["download_status"] = "failed"
            item["download_error"] = "No document URL"
            self.stats["failed"] += 1
            return item

        try:
            # Create request with proper headers
            request = Request(
                url=document_url,
                callback=lambda r: r,  # Dummy callback
                dont_filter=True,
                meta={
                    "download_timeout": 300,
                    "handle_httpstatus_list": [200, 404, 403, 500],
                },
                headers={
                    "Accept": "application/pdf,*/*",
                    "Referer": item.get("source_url", ""),
                },
            )

            # Use Scrapy's downloader
            response = yield self.crawler.engine.download(request)

            if response.status == 200:
                local_path = self._save_response(response, item)

                if local_path:
                    item["local_path"] = local_path
                    item["download_status"] = "success"
                    item["file_size"] = os.path.getsize(local_path)
                    self.stats["successful"] += 1
                    self.stats["total_bytes"] += item["file_size"]

                    self.logger.info(
                        f"Downloaded: {item.get('filename')} "
                        f"({item['file_size'] / 1024:.1f} KB)"
                    )
                else:
                    item["download_status"] = "failed"
                    item["download_error"] = "Failed to save file"
                    self.stats["failed"] += 1
            else:
                item["download_status"] = "failed"
                item["download_error"] = f"HTTP {response.status}"
                self.stats["failed"] += 1
                self.logger.warning(
                    f"Download failed: HTTP {response.status} for {item.get('filename')}"
                )

        except Exception as e:
            item["download_status"] = "failed"
            item["download_error"] = str(e)
            self.stats["failed"] += 1
            error_type = type(e).__name__
            self.logger.error(
                f"Download failed [{error_type}] for {item.get('filename', 'unknown')}: {e}"
            )

        return item

    def _save_response(self, response: Response, item: DocumentItem) -> Optional[str]:
        """
        Save response body to a temporary file.

        Args:
            response: Scrapy response object
            item: DocumentItem with metadata

        Returns:
            Path to saved file or None on failure
        """
        # Check content type
        content_type = response.headers.get(b"Content-Type", b"").decode()
        content_type = content_type.split(";")[0].strip()
        item["content_type"] = content_type

        # Check response size
        body_size = len(response.body)
        if body_size > self.MAX_FILE_SIZE:
            self.logger.warning(
                f"File too large: {body_size} bytes for {item.get('filename')}"
            )
            return None

        if body_size == 0:
            self.logger.warning(f"Empty response for {item.get('filename')}")
            return None

        # Generate temp filename
        filename = clean_filename(item.get("filename", "document.pdf"))
        if not filename:
            filename = "document.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Add unique prefix to avoid collisions
        temp_path = os.path.join(self.temp_dir, f"{os.getpid()}_{filename}")

        # Handle duplicate filenames
        counter = 1
        base_path = temp_path
        while os.path.exists(temp_path):
            name, ext = os.path.splitext(base_path)
            temp_path = f"{name}_{counter}{ext}"
            counter += 1

        # Write file
        try:
            with open(temp_path, "wb") as f:
                f.write(response.body)
            return temp_path
        except Exception as e:
            self.logger.error(f"Failed to write file {temp_path}: {e}")
            return None

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"PDF download stats: {self.stats['total_downloads']} total, "
            f"{self.stats['successful']} successful, {self.stats['failed']} failed, "
            f"{self.stats['total_bytes'] / (1024*1024):.2f} MB downloaded"
        )

        spider.crawler.stats.set_value(
            "pdf_download/total", self.stats["total_downloads"]
        )
        spider.crawler.stats.set_value(
            "pdf_download/successful", self.stats["successful"]
        )
        spider.crawler.stats.set_value(
            "pdf_download/failed", self.stats["failed"]
        )
        spider.crawler.stats.set_value(
            "pdf_download/total_bytes", self.stats["total_bytes"]
        )
