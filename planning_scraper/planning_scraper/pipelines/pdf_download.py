"""
PDF Download Pipeline - downloads matching PDF documents.

This pipeline runs after DocumentFilterPipeline (priority 200).
Downloads PDFs to temporary storage for compression and S3 upload.
"""

import logging
import tempfile
import os
from pathlib import Path
from typing import Optional

import scrapy
from scrapy.exceptions import DropItem

from ..items.document import DocumentItem
from ..utils.text_cleaner import clean_filename


class PDFDownloadPipeline:
    """
    Pipeline that downloads PDF documents to temporary storage.

    Features:
    - Streaming download for large files
    - Content-type validation
    - Retry on failure
    - Temporary file management
    """

    # Maximum file size to download (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    # Chunk size for streaming (8KB)
    CHUNK_SIZE = 8192

    # Valid content types for PDFs
    VALID_CONTENT_TYPES = [
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",  # Some servers use this for PDFs
    ]

    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir
        self.logger = logging.getLogger(__name__)
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
        return cls(temp_dir=temp_dir)

    def open_spider(self, spider):
        """Create temp directory when spider opens."""
        if self.temp_dir:
            os.makedirs(self.temp_dir, exist_ok=True)
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="planning_pdfs_")
        self.logger.info(f"PDF temp directory: {self.temp_dir}")

    def process_item(self, item, spider):
        """
        Download a PDF document.

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
            local_path = self._download_pdf(document_url, item, spider)

            if local_path:
                item["local_path"] = local_path
                item["download_status"] = "success"
                item["file_size"] = os.path.getsize(local_path)
                self.stats["successful"] += 1
                self.stats["total_bytes"] += item["file_size"]

                self.logger.debug(
                    f"Downloaded: {item.get('filename')} "
                    f"({item['file_size']} bytes)"
                )
            else:
                item["download_status"] = "failed"
                item["download_error"] = "Download returned no data"
                self.stats["failed"] += 1

        except Exception as e:
            item["download_status"] = "failed"
            item["download_error"] = str(e)
            self.stats["failed"] += 1
            self.logger.error(f"Download failed for {document_url}: {e}")

        return item

    def _download_pdf(
        self, url: str, item: DocumentItem, spider
    ) -> Optional[str]:
        """
        Download a PDF file to temporary storage.

        Args:
            url: Document URL
            item: DocumentItem with metadata
            spider: Spider instance

        Returns:
            Path to downloaded file or None on failure
        """
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # Set up session with retry
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

        # Request headers
        headers = {
            "User-Agent": spider.settings.get(
                "USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ),
            "Accept": "application/pdf,*/*",
        }

        # Stream the download
        response = session.get(
            url,
            headers=headers,
            stream=True,
            timeout=(10, 300),  # 10s connect, 300s read
            allow_redirects=True,
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        item["content_type"] = content_type

        if content_type not in self.VALID_CONTENT_TYPES:
            # Some servers don't set content-type correctly, check URL
            if not url.lower().endswith(".pdf"):
                self.logger.warning(
                    f"Invalid content type for {url}: {content_type}"
                )

        # Check content length if available
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {int(content_length)} bytes "
                f"(max: {self.MAX_FILE_SIZE})"
            )

        # Generate temp filename
        filename = clean_filename(item.get("filename", "document.pdf"))
        if not filename:
            filename = "document.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        temp_path = os.path.join(self.temp_dir, f"{os.getpid()}_{filename}")

        # Stream to file
        total_size = 0
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                if chunk:
                    total_size += len(chunk)
                    if total_size > self.MAX_FILE_SIZE:
                        f.close()
                        os.remove(temp_path)
                        raise ValueError(
                            f"File exceeded max size during download: "
                            f"{total_size} bytes"
                        )
                    f.write(chunk)

        return temp_path

    def close_spider(self, spider):
        """Log statistics and clean up when spider closes."""
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
