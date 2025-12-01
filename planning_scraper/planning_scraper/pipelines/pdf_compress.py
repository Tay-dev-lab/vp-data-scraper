"""
PDF Compress Pipeline - compresses large PDF files using Ghostscript.

This pipeline runs after PDFDownloadPipeline (priority 300).
Compresses files larger than SIZE_THRESHOLD before S3 upload.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..items.document import DocumentItem


class PDFCompressPipeline:
    """
    Pipeline that compresses large PDF files using Ghostscript.

    Requirements:
    - Ghostscript must be installed: brew install ghostscript (macOS)
      or apt-get install ghostscript (Ubuntu)

    Settings:
    - PDF_COMPRESS_THRESHOLD: Size threshold in bytes (default 10MB)
    - PDF_COMPRESS_DPI: Target DPI for images (default 150)
    """

    # Default threshold: 10MB
    DEFAULT_THRESHOLD = 10 * 1024 * 1024

    # Default DPI for image downsampling
    DEFAULT_DPI = 150

    # Timeout for compression (2 minutes)
    COMPRESS_TIMEOUT = 120

    def __init__(
        self,
        threshold: int = DEFAULT_THRESHOLD,
        target_dpi: int = DEFAULT_DPI,
    ):
        self.threshold = threshold
        self.target_dpi = target_dpi
        self.logger = logging.getLogger(__name__)
        self.gs_available = self._check_ghostscript()
        self.stats = {
            "total_processed": 0,
            "compressed": 0,
            "skipped_small": 0,
            "failed": 0,
            "bytes_saved": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        threshold = crawler.settings.getint(
            "PDF_COMPRESS_THRESHOLD", cls.DEFAULT_THRESHOLD
        )
        target_dpi = crawler.settings.getint(
            "PDF_COMPRESS_DPI", cls.DEFAULT_DPI
        )
        return cls(threshold=threshold, target_dpi=target_dpi)

    def _check_ghostscript(self) -> bool:
        """Check if Ghostscript is available."""
        try:
            result = subprocess.run(
                ["gs", "--version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                self.logger.info(f"Ghostscript available: version {version}")
                return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        self.logger.warning(
            "Ghostscript not available - PDF compression disabled. "
            "Install with: brew install ghostscript (macOS) or "
            "apt-get install ghostscript (Ubuntu)"
        )
        return False

    def process_item(self, item, spider):
        """
        Compress a PDF if it exceeds the size threshold.

        Only processes DocumentItems with successful downloads.
        """
        # Only process DocumentItems
        if not isinstance(item, DocumentItem):
            return item

        # Only process successfully downloaded items
        if item.get("download_status") != "success":
            return item

        local_path = item.get("local_path")
        if not local_path or not os.path.exists(local_path):
            return item

        self.stats["total_processed"] += 1

        file_size = os.path.getsize(local_path)

        # Skip if under threshold
        if file_size < self.threshold:
            self.stats["skipped_small"] += 1
            self.logger.debug(
                f"Skipping compression for {item.get('filename')} "
                f"({file_size} bytes < {self.threshold} threshold)"
            )
            return item

        # Skip if Ghostscript not available
        if not self.gs_available:
            return item

        # Compress the PDF
        item["original_size"] = file_size
        compressed_path = self._compress_pdf(local_path)

        if compressed_path:
            compressed_size = os.path.getsize(compressed_path)

            # Only use compressed version if it's actually smaller
            if compressed_size < file_size:
                # Remove original, replace with compressed
                os.remove(local_path)
                item["local_path"] = compressed_path
                item["compressed"] = True
                item["compressed_size"] = compressed_size
                item["file_size"] = compressed_size

                bytes_saved = file_size - compressed_size
                self.stats["compressed"] += 1
                self.stats["bytes_saved"] += bytes_saved

                self.logger.info(
                    f"Compressed {item.get('filename')}: "
                    f"{file_size} -> {compressed_size} bytes "
                    f"(saved {bytes_saved / 1024:.1f} KB, "
                    f"{(1 - compressed_size/file_size) * 100:.1f}%)"
                )
            else:
                # Compressed is larger - keep original
                os.remove(compressed_path)
                item["compressed"] = False
                self.logger.debug(
                    f"Compression didn't help for {item.get('filename')}: "
                    f"original {file_size} bytes, compressed {compressed_size} bytes"
                )
        else:
            self.stats["failed"] += 1
            item["compressed"] = False

        return item

    def _compress_pdf(self, input_path: str) -> Optional[str]:
        """
        Compress a PDF using Ghostscript.

        Args:
            input_path: Path to the input PDF

        Returns:
            Path to compressed PDF or None on failure
        """
        # Create output path
        output_fd, output_path = tempfile.mkstemp(suffix=".pdf")
        os.close(output_fd)

        try:
            cmd = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/ebook",  # Good balance for drawings
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dDownsampleColorImages=true",
                f"-dColorImageResolution={self.target_dpi}",
                "-dDownsampleGrayImages=true",
                f"-dGrayImageResolution={self.target_dpi}",
                "-dDownsampleMonoImages=true",
                f"-dMonoImageResolution={self.target_dpi}",
                f"-sOutputFile={output_path}",
                input_path,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.COMPRESS_TIMEOUT,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            else:
                error = result.stderr.decode() if result.stderr else "Unknown error"
                self.logger.warning(f"Ghostscript compression failed: {error}")
                if os.path.exists(output_path):
                    os.remove(output_path)
                return None

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Compression timed out for {input_path}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

        except Exception as e:
            self.logger.error(f"Compression error: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"PDF compression stats: {self.stats['total_processed']} processed, "
            f"{self.stats['compressed']} compressed, "
            f"{self.stats['skipped_small']} skipped (small), "
            f"{self.stats['failed']} failed, "
            f"{self.stats['bytes_saved'] / (1024*1024):.2f} MB saved"
        )

        spider.crawler.stats.set_value(
            "pdf_compress/total", self.stats["total_processed"]
        )
        spider.crawler.stats.set_value(
            "pdf_compress/compressed", self.stats["compressed"]
        )
        spider.crawler.stats.set_value(
            "pdf_compress/bytes_saved", self.stats["bytes_saved"]
        )
