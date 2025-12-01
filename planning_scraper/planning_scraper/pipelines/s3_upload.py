"""
S3 Upload Pipeline - uploads PDFs to Amazon S3.

This pipeline runs after PDFCompressPipeline (priority 400).
Uploads PDFs with structured keys for organization and Lambda processing.
"""

import logging
import os
import re
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from ..items.document import DocumentItem
from ..utils.id_generator import generate_short_id


class S3UploadPipeline:
    """
    Pipeline that uploads PDF documents to Amazon S3.

    S3 Key Structure:
        documents/{council_name}/{application_reference}/{document_type}/{id}_{filename}.pdf

    Example:
        documents/doncaster/25-00123-FUL/floor_plan/a1b2c3d4_ground-floor-plan.pdf

    Settings:
    - S3_BUCKET_NAME: Target S3 bucket name
    - AWS_ACCESS_KEY_ID: AWS access key
    - AWS_SECRET_ACCESS_KEY: AWS secret key
    - AWS_REGION: AWS region (default: eu-west-2)
    """

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region: str = "eu-west-2",
    ):
        self.bucket_name = bucket_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region = region
        self.s3_client = None
        self.logger = logging.getLogger(__name__)
        self.stats = {
            "total_uploads": 0,
            "successful": 0,
            "failed": 0,
            "total_bytes": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        return cls(
            bucket_name=crawler.settings.get("S3_BUCKET_NAME"),
            aws_access_key_id=crawler.settings.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=crawler.settings.get("AWS_SECRET_ACCESS_KEY"),
            region=crawler.settings.get("AWS_REGION", "eu-west-2"),
        )

    def open_spider(self, spider):
        """Initialize S3 client when spider opens."""
        spider.logger.info("=" * 60)
        spider.logger.info("S3 CONFIGURATION")
        spider.logger.info("=" * 60)

        if not self.bucket_name:
            spider.logger.warning("  Status: DISABLED")
            spider.logger.warning("  Reason: S3_BUCKET_NAME not configured")
            spider.logger.info("=" * 60)
            return

        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region,
            )
            # Test connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)

            spider.logger.info("  Status: CONNECTED")
            spider.logger.info(f"  Bucket: {self.bucket_name}")
            spider.logger.info(f"  Region: {self.region}")
            spider.logger.info(f"  Key Pattern: documents/{{council}}/{{app_ref}}/{{doc_type}}/{{id}}_{{filename}}.pdf")
            spider.logger.info("=" * 60)
        except ClientError as e:
            spider.logger.error("  Status: FAILED")
            spider.logger.error(f"  Bucket: {self.bucket_name}")
            spider.logger.error(f"  Error: {e}")
            spider.logger.info("=" * 60)
            self.s3_client = None

    def process_item(self, item, spider):
        """
        Upload a PDF to S3.

        Only processes DocumentItems with successful downloads.
        """
        # Only process DocumentItems
        if not isinstance(item, DocumentItem):
            return item

        # Only process successfully downloaded items
        if item.get("download_status") != "success":
            return item

        # Skip if S3 not configured
        if not self.s3_client:
            item["upload_status"] = "skipped"
            item["upload_error"] = "S3 not configured"
            return item

        local_path = item.get("local_path")
        if not local_path or not os.path.exists(local_path):
            item["upload_status"] = "failed"
            item["upload_error"] = "Local file not found"
            return item

        self.stats["total_uploads"] += 1

        try:
            # Generate S3 key
            s3_key = self._generate_s3_key(item)

            # Upload file
            file_size = os.path.getsize(local_path)

            self.s3_client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": "application/pdf",
                    "Metadata": {
                        "application_reference": item.get("application_reference", ""),
                        "council_name": item.get("council_name", ""),
                        "document_type": item.get("document_type", ""),
                        "original_filename": item.get("filename", ""),
                    },
                },
            )

            item["s3_bucket"] = self.bucket_name
            item["s3_key"] = s3_key
            item["s3_url"] = f"s3://{self.bucket_name}/{s3_key}"
            item["upload_status"] = "success"

            self.stats["successful"] += 1
            self.stats["total_bytes"] += file_size

            self.logger.debug(
                f"Uploaded to S3: {s3_key} ({file_size} bytes)"
            )

            # Clean up local file after successful upload
            try:
                os.remove(local_path)
            except OSError:
                pass

        except ClientError as e:
            item["upload_status"] = "failed"
            item["upload_error"] = str(e)
            self.stats["failed"] += 1
            self.logger.error(f"S3 upload failed: {e}")

        except Exception as e:
            item["upload_status"] = "failed"
            item["upload_error"] = str(e)
            self.stats["failed"] += 1
            self.logger.error(f"S3 upload error: {e}")

        return item

    def _generate_s3_key(self, item: DocumentItem) -> str:
        """
        Generate S3 key for a document.

        Format: documents/{council}/{app_ref}/{doc_type}/{id}_{filename}.pdf
        """
        council = self._sanitize_key_component(
            item.get("council_name", "unknown")
        )
        app_ref = self._sanitize_key_component(
            item.get("application_reference", "unknown")
        )
        doc_type = self._sanitize_key_component(
            item.get("document_type", "unknown")
        )
        filename = self._sanitize_key_component(
            item.get("filename", "document.pdf")
        )

        # Ensure filename ends with .pdf
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Add unique ID prefix to avoid collisions
        unique_id = generate_short_id(8)

        return f"documents/{council}/{app_ref}/{doc_type}/{unique_id}_{filename}"

    def _sanitize_key_component(self, value: str) -> str:
        """
        Sanitize a value for use in an S3 key.

        - Lowercase
        - Replace spaces and special chars with underscore
        - Remove consecutive underscores
        - Limit length
        """
        if not value:
            return "unknown"

        # Lowercase and replace problematic characters
        value = value.lower()
        value = re.sub(r"[^a-z0-9._-]", "_", value)
        value = re.sub(r"_+", "_", value)
        value = value.strip("_")

        # Limit length
        return value[:100] if value else "unknown"

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"S3 upload stats: {self.stats['total_uploads']} total, "
            f"{self.stats['successful']} successful, {self.stats['failed']} failed, "
            f"{self.stats['total_bytes'] / (1024*1024):.2f} MB uploaded"
        )

        spider.crawler.stats.set_value(
            "s3_upload/total", self.stats["total_uploads"]
        )
        spider.crawler.stats.set_value(
            "s3_upload/successful", self.stats["successful"]
        )
        spider.crawler.stats.set_value(
            "s3_upload/failed", self.stats["failed"]
        )
        spider.crawler.stats.set_value(
            "s3_upload/total_bytes", self.stats["total_bytes"]
        )
