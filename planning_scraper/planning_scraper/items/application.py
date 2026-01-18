"""
Planning Application Item - represents a planning application scraped from a portal.

Only applications that pass the residential filter AND have matching documents
will be stored in Supabase.
"""

import scrapy
from itemloaders.processors import TakeFirst, MapCompose

from ..utils.text_cleaner import clean_text


class PlanningApplicationItem(scrapy.Item):
    """
    Scrapy Item for a planning application.

    This is a simplified version focusing on key fields needed for context.
    Only applications with at least one matching PDF document will be stored.
    """

    # Core identification
    application_reference = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    application_url = scrapy.Field(output_processor=TakeFirst())
    council_name = scrapy.Field(output_processor=TakeFirst())

    # Location
    site_address = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    postcode = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    ward = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    parish = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )

    # Application details
    application_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    proposal = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    status = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    decision = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )

    # Key dates
    registration_date = scrapy.Field(output_processor=TakeFirst())
    decision_date = scrapy.Field(output_processor=TakeFirst())
    valid_from = scrapy.Field(output_processor=TakeFirst())

    # People (minimal)
    applicant_name = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    agent_name = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )
    case_officer = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst(),
    )

    # Project organization (for targeted scrapes)
    project_tag = scrapy.Field(output_processor=TakeFirst())

    # Internal tracking (not stored in Supabase)
    _supabase_id = scrapy.Field()  # Set by SupabasePipeline after insert
    _portal_framework = scrapy.Field()  # e.g., "idox", "agile", "aspx"
    _scraped_at = scrapy.Field()  # Timestamp when scraped
    _has_documents = scrapy.Field()  # Flag set after document processing
    _llm_classification = scrapy.Field()  # LLM classification result (dict)
