"""
Run Logger Extension - creates lightweight logs of spider runs.

Logs:
- Run summary (start/end times, items scraped)
- Failed URLs (non-200 status codes)
- Per-council summary
- Errors and exceptions
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from scrapy import signals
from scrapy.http import Response, Request


class RunLoggerExtension:
    """
    Extension that logs spider run summaries and failures.

    Creates a JSON log file for each run with:
    - Run metadata (times, totals)
    - Failed requests (non-200 responses)
    - Per-council breakdown
    - Errors encountered
    """

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # Track failures
        self.failed_requests: List[Dict[str, Any]] = []
        self.council_stats: Dict[str, Dict[str, int]] = {}
        self.errors: List[Dict[str, Any]] = []

        # Run info
        self.start_time = None
        self.spider_name = None

    @classmethod
    def from_crawler(cls, crawler):
        log_dir = crawler.settings.get("RUN_LOG_DIR", "logs/runs")
        ext = cls(log_dir)

        # Connect signals
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(ext.response_received, signal=signals.response_received)
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.item_dropped, signal=signals.item_dropped)
        crawler.signals.connect(ext.spider_error, signal=signals.spider_error)

        return ext

    def spider_opened(self, spider):
        """Record spider start."""
        self.start_time = datetime.utcnow()
        self.spider_name = spider.name
        spider.logger.info(f"Run logger active - logs will be saved to {self.log_dir}")

    def response_received(self, response: Response, request: Request, spider):
        """Track non-200 responses."""
        council = request.meta.get("council_name", "unknown")

        # Initialize council stats
        if council not in self.council_stats:
            self.council_stats[council] = {
                "requests": 0,
                "success": 0,
                "failed": 0,
                "items": 0,
            }

        self.council_stats[council]["requests"] += 1

        # Track failures
        if response.status != 200:
            self.council_stats[council]["failed"] += 1

            # Only log actual failures, not redirects
            if response.status >= 400:
                self.failed_requests.append({
                    "url": response.url,
                    "status": response.status,
                    "council": council,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                # Log immediately for visibility
                spider.logger.warning(
                    f"HTTP {response.status} from {council}: {response.url[:80]}..."
                )
        else:
            self.council_stats[council]["success"] += 1

    def item_scraped(self, item, response, spider):
        """Track scraped items per council."""
        council = item.get("council_name", "unknown")
        if council in self.council_stats:
            self.council_stats[council]["items"] += 1

    def item_dropped(self, item, response, exception, spider):
        """Track dropped items."""
        pass  # Already tracked by pipelines

    def spider_error(self, failure, response, spider):
        """Track spider errors."""
        self.errors.append({
            "url": response.url if response else "unknown",
            "error": str(failure.value),
            "type": failure.type.__name__,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def spider_closed(self, spider, reason):
        """Write run summary to log file."""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        # Get stats from crawler
        stats = spider.crawler.stats.get_stats()

        # Build summary
        run_summary = {
            "run_id": self.start_time.strftime("%Y%m%d_%H%M%S"),
            "spider": self.spider_name,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "close_reason": reason,

            "totals": {
                "requests": stats.get("downloader/request_count", 0),
                "responses": stats.get("downloader/response_count", 0),
                "items_scraped": stats.get("item_scraped_count", 0),
                "items_dropped": stats.get("item_dropped_count", 0),
            },

            "response_codes": {
                "200": stats.get("downloader/response_status_count/200", 0),
                "302": stats.get("downloader/response_status_count/302", 0),
                "403": stats.get("downloader/response_status_count/403", 0),
                "404": stats.get("downloader/response_status_count/404", 0),
                "429": stats.get("downloader/response_status_count/429", 0),
                "500": stats.get("downloader/response_status_count/500", 0),
            },

            "pipeline_stats": {
                "applications_total": stats.get("application_filter/total", 0),
                "applications_accepted": stats.get("application_filter/accepted", 0),
                "applications_rejected": stats.get("application_filter/rejected", 0),
                "documents_total": stats.get("document_filter/total", 0),
                "documents_accepted": stats.get("document_filter/accepted", 0),
                "pdfs_downloaded": stats.get("pdf_download/successful", 0),
                "pdfs_uploaded": stats.get("s3_upload/successful", 0),
                "supabase_stored": stats.get("supabase/applications_stored", 0),
            },

            "retries": {
                "total": stats.get("retry/count", 0),
                "max_reached": stats.get("retry/max_reached", 0),
            },

            "failed_requests": self.failed_requests,
            "council_breakdown": self.council_stats,
            "errors": self.errors,
        }

        # Write to file
        log_file = self.log_dir / f"run_{run_summary['run_id']}.json"
        with open(log_file, "w") as f:
            json.dump(run_summary, f, indent=2)

        spider.logger.info(f"Run log saved to: {log_file}")

        # Print summary to console
        self._print_summary(spider, run_summary)

    def _print_summary(self, spider, summary: Dict):
        """Print a readable summary to the console."""
        spider.logger.info("")
        spider.logger.info("=" * 60)
        spider.logger.info("RUN SUMMARY")
        spider.logger.info("=" * 60)
        spider.logger.info(f"  Duration: {summary['duration_seconds']:.1f}s")
        spider.logger.info(f"  Requests: {summary['totals']['requests']}")
        spider.logger.info(f"  Items Scraped: {summary['totals']['items_scraped']}")
        spider.logger.info(f"  Items Dropped: {summary['totals']['items_dropped']}")
        spider.logger.info("")

        # Response codes
        spider.logger.info("Response Codes:")
        for code, count in summary["response_codes"].items():
            if count > 0:
                status = "OK" if code == "200" else "ISSUE"
                spider.logger.info(f"  {code}: {count} [{status}]")

        # Failed requests
        if summary["failed_requests"]:
            spider.logger.info("")
            spider.logger.info(f"Failed Requests ({len(summary['failed_requests'])}):")
            for fail in summary["failed_requests"][:10]:
                spider.logger.info(f"  [{fail['status']}] {fail['council']}: {fail['url'][:60]}...")
            if len(summary["failed_requests"]) > 10:
                spider.logger.info(f"  ... and {len(summary['failed_requests']) - 10} more")

        # Council breakdown
        spider.logger.info("")
        spider.logger.info("Council Summary:")
        for council, stats in sorted(summary["council_breakdown"].items()):
            spider.logger.info(
                f"  {council}: {stats['requests']} req, "
                f"{stats['success']} ok, {stats['failed']} fail, "
                f"{stats['items']} items"
            )

        spider.logger.info("=" * 60)
