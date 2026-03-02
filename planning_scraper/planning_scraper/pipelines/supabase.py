"""
Supabase Pipeline - stores application and document metadata.

This pipeline runs LAST (priority 500) after all other processing.
Only stores applications that have at least one matching document.

IMPORTANT: Handles race conditions where documents may arrive before their
parent application has been processed through the pipeline. Documents are
queued and processed when their parent application arrives.
"""

import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..items.application import PlanningApplicationItem
from ..items.document import DocumentItem


class SupabasePipeline:
    """
    Pipeline that stores metadata in Supabase.

    Design:
    - Applications are held until we see if they have documents
    - Only applications with at least one uploaded document are stored
    - Documents are linked to applications via foreign key
    - Documents that arrive before their parent are queued

    Settings:
    - SUPABASE_URL: Supabase project URL
    - SUPABASE_KEY: Supabase service key
    - SUPABASE_STORE_APPS_WITHOUT_DOCS: Store apps even without documents
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        store_apps_without_docs: bool = False,
    ):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.store_apps_without_docs = store_apps_without_docs
        self.client = None
        self.logger = logging.getLogger(__name__)

        # Track pending applications waiting for documents
        self.pending_apps: Dict[str, PlanningApplicationItem] = {}

        # Track which applications have been stored in Supabase
        self.apps_with_docs: Dict[str, str] = {}  # app_key -> supabase_id

        # Queue for documents that arrive before their parent application
        self.queued_docs: Dict[str, List[DocumentItem]] = defaultdict(list)

        self.stats = {
            "applications_stored": 0,
            "applications_dropped": 0,
            "documents_stored": 0,
            "documents_queued": 0,
            "queued_docs_processed": 0,
            "errors": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        return cls(
            supabase_url=crawler.settings.get("SUPABASE_URL"),
            supabase_key=crawler.settings.get("SUPABASE_KEY"),
            store_apps_without_docs=crawler.settings.getbool(
                "SUPABASE_STORE_APPS_WITHOUT_DOCS", False
            ),
        )

    def open_spider(self, spider):
        """Initialize Supabase client when spider opens."""
        spider.logger.info("=" * 60)
        spider.logger.info("SUPABASE CONFIGURATION")
        spider.logger.info("=" * 60)

        if not self.supabase_url or not self.supabase_key:
            spider.logger.warning("  Status: DISABLED")
            spider.logger.warning("  Reason: SUPABASE_URL or SUPABASE_KEY not configured")
            spider.logger.info("=" * 60)
            return

        try:
            from supabase import create_client

            self.client = create_client(self.supabase_url, self.supabase_key)

            # Test connection by checking if we can access the table
            test_result = self.client.table("planning_applications").select("id").limit(1).execute()

            spider.logger.info("  Status: CONNECTED")
            spider.logger.info(f"  URL: {self.supabase_url[:50]}...")
            spider.logger.info("  Tables: planning_applications, application_documents")
            spider.logger.info("=" * 60)
        except Exception as e:
            spider.logger.error("  Status: FAILED")
            spider.logger.error(f"  Error: {e}")
            spider.logger.info("=" * 60)
            self.client = None

    def process_item(self, item, spider):
        """
        Process an item - store in Supabase if appropriate.

        Applications are held pending; documents trigger storage.
        """
        if isinstance(item, PlanningApplicationItem):
            return self._handle_application(item)
        elif isinstance(item, DocumentItem):
            return self._handle_document(item)
        return item

    def _handle_application(self, item: PlanningApplicationItem):
        """
        Handle a PlanningApplicationItem.

        Hold the application pending - it will only be stored
        if we receive at least one document for it.

        Also processes any documents that arrived before this application.
        """
        app_ref = item.get("application_reference")
        council = item.get("council_name")

        if not app_ref:
            return item

        # Create composite key
        key = f"{council}:{app_ref}"

        # Store pending - will be committed when we see a document
        self.pending_apps[key] = item
        self.logger.debug(f"Holding application pending documents: {key}")

        # Check if there are queued documents waiting for this application
        if key in self.queued_docs and self.queued_docs[key]:
            queued_count = len(self.queued_docs[key])
            self.logger.info(
                f"Processing {queued_count} queued document(s) for application {key}"
            )

            # Process each queued document
            for doc_item in self.queued_docs[key]:
                self._process_document_for_app(doc_item, key)
                self.stats["queued_docs_processed"] += 1

            # Clear the queue for this application
            del self.queued_docs[key]

        return item

    def _handle_document(self, item: DocumentItem):
        """
        Handle a DocumentItem.

        If this is the first document for an application, store the application.
        Then store the document linked to the application.

        If the parent application hasn't arrived yet, queue the document.
        """
        if not self.client:
            return item

        # Only process successfully uploaded documents
        if item.get("upload_status") != "success":
            self.logger.debug(
                f"Skipping document {item.get('filename')} - upload_status: {item.get('upload_status')}"
            )
            return item

        app_ref = item.get("application_reference")
        council = item.get("council_name")

        if not app_ref:
            return item

        key = f"{council}:{app_ref}"

        # Check if parent application has arrived
        if key not in self.pending_apps and key not in self.apps_with_docs:
            # Application hasn't arrived yet - queue the document
            self.queued_docs[key].append(item)
            self.stats["documents_queued"] += 1
            self.logger.debug(
                f"Document {item.get('filename')} queued - "
                f"parent application {key} not yet received "
                f"(queue size: {len(self.queued_docs[key])})"
            )
            return item

        # Process the document
        self._process_document_for_app(item, key)
        return item

    def _process_document_for_app(self, item: DocumentItem, key: str):
        """
        Process a document for a known application.

        Stores the application if needed, then stores the document.
        """
        try:
            # Check if we need to store the application first
            if key not in self.apps_with_docs:
                app_id = self._store_application(key)
                if app_id:
                    self.apps_with_docs[key] = app_id
                else:
                    self.logger.warning(
                        f"Could not store application for document: {key}"
                    )
                    return

            # Store the document
            app_id = self.apps_with_docs.get(key)
            if app_id:
                self._store_document(item, app_id)

        except Exception as e:
            self.logger.error(f"Error storing to Supabase: {e}")
            self.stats["errors"] += 1

    def _store_application(self, key: str) -> Optional[str]:
        """
        Store a pending application to Supabase.

        Returns the Supabase UUID of the stored application.
        """
        if key not in self.pending_apps:
            # Application might have been rejected by filter
            self.logger.debug(f"No pending application for key: {key}")
            return None

        item = self.pending_apps.pop(key)

        data = {
            "application_reference": item.get("application_reference"),
            "council_name": item.get("council_name"),
            "site_address": item.get("site_address"),
            "postcode": item.get("postcode"),
            "ward": item.get("ward"),
            "parish": item.get("parish"),
            "application_type": item.get("application_type"),
            "proposal": item.get("proposal"),
            "status": item.get("status"),
            "decision": item.get("decision"),
            "registration_date": item.get("registration_date"),
            "decision_date": item.get("decision_date"),
            "applicant_name": item.get("applicant_name"),
            "agent_name": item.get("agent_name"),
            "application_url": item.get("application_url"),
            "project_tag": item.get("project_tag"),
            "scraped_at": datetime.utcnow().isoformat(),
        }

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        try:
            result = (
                self.client.table("planning_applications")
                .upsert(data, on_conflict="council_name,application_reference")
                .execute()
            )

            if result.data:
                app_id = result.data[0]["id"]
                item["_supabase_id"] = app_id
                self.stats["applications_stored"] += 1
                self.logger.debug(f"Stored application: {key} -> {app_id}")
                return app_id

        except Exception as e:
            self.logger.error(f"Failed to store application {key}: {e}")
            self.stats["errors"] += 1

        return None

    def _store_document(self, item: DocumentItem, app_id: str):
        """
        Store a document record linked to an application.
        """
        data = {
            "application_id": app_id,
            "s3_bucket": item.get("s3_bucket"),
            "s3_key": item.get("s3_key"),
            "document_name": item.get("filename"),
            "document_type": item.get("document_type"),
            "file_size_bytes": item.get("file_size"),
            "project_tag": item.get("project_tag"),
        }

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        try:
            result = (
                self.client.table("application_documents")
                .upsert(data, on_conflict="s3_bucket,s3_key")
                .execute()
            )

            if result.data:
                item["_document_id"] = result.data[0]["id"]
                self.stats["documents_stored"] += 1
                self.logger.debug(
                    f"Stored document: {item.get('filename')} -> {result.data[0]['id']}"
                )

        except Exception as e:
            self.logger.error(f"Failed to store document: {e}")
            self.stats["errors"] += 1

    def close_spider(self, spider):
        """Log statistics and report dropped applications when spider closes."""
        # Optionally store applications without documents
        if self.store_apps_without_docs and self.pending_apps and self.client:
            self.logger.info(
                f"Storing {len(self.pending_apps)} applications without documents "
                f"(SUPABASE_STORE_APPS_WITHOUT_DOCS=true)"
            )
            for key in list(self.pending_apps.keys()):
                if key not in self.apps_with_docs:
                    app_id = self._store_application(key)
                    if app_id:
                        self.apps_with_docs[key] = app_id

        # Count applications that were dropped (had no documents)
        self.stats["applications_dropped"] = len(self.pending_apps)

        # Log any orphaned queued documents (shouldn't happen normally)
        orphaned_docs = sum(len(docs) for docs in self.queued_docs.values())
        if orphaned_docs > 0:
            self.logger.warning(
                f"WARNING: {orphaned_docs} document(s) remain queued - "
                f"their parent applications were never received. "
                f"This may indicate a race condition or filtering issue."
            )
            for key, docs in self.queued_docs.items():
                self.logger.warning(f"  - {key}: {len(docs)} document(s)")

        if self.pending_apps:
            self.logger.info(
                f"Dropped {len(self.pending_apps)} applications with no matching documents"
            )

        self.logger.info(
            f"Supabase stats: {self.stats['applications_stored']} applications stored, "
            f"{self.stats['applications_dropped']} dropped (no docs), "
            f"{self.stats['documents_stored']} documents stored, "
            f"{self.stats['documents_queued']} documents queued, "
            f"{self.stats['queued_docs_processed']} queued docs processed, "
            f"{self.stats['errors']} errors"
        )

        spider.crawler.stats.set_value(
            "supabase/applications_stored", self.stats["applications_stored"]
        )
        spider.crawler.stats.set_value(
            "supabase/applications_dropped", self.stats["applications_dropped"]
        )
        spider.crawler.stats.set_value(
            "supabase/documents_stored", self.stats["documents_stored"]
        )
        spider.crawler.stats.set_value(
            "supabase/documents_queued", self.stats["documents_queued"]
        )
        spider.crawler.stats.set_value(
            "supabase/queued_docs_processed", self.stats["queued_docs_processed"]
        )
        spider.crawler.stats.set_value(
            "supabase/errors", self.stats["errors"]
        )
        spider.crawler.stats.set_value(
            "supabase/orphaned_queued_docs", orphaned_docs
        )
