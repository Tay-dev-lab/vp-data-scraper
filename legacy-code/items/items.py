# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy import Item, Field
from itemloaders.processors import MapCompose, Join, TakeFirst
from w3lib.html import remove_tags
from datetime import datetime
import re


def clean_text(text):
    """
    Universal cleaning function that removes excessive whitespace, newlines,
    HTML tags and other unwanted characters from scraped text.
    
    Args:
        text: The text to clean (string or None)
        
    Returns:
        Cleaned text as string, or None if input was None
    """
    if text is None:
        return None
    
    # Remove HTML tags if any
    text = remove_tags(text)
    
    # Remove excessive whitespace, newlines and other whitespace characters
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


class BaseItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass



class PlanningApplicationItem(Item):
    # Basic Application Details
        # Application Progress Summary fields

    application_url = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
        # Add these missing fields
    council_name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    application_reference = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
        # Add the missing field
    application_id = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    proposal = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Location Details
    site_address = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    location_coordinates = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    ward = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    parish = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    
    # Application Status
    status = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    decision = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
          
    # Additional Details
    application_type = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    application_type_id = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    development_type = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )







    # Dates - now treated as strings with clean_text
    registration_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    valid_from = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    decision_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    dispatch_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    advert_expiry_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )



    appeal_submitted = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    appeal_decision = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    division = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    existing_land_use = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    proposed_land_use = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    committee_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    conservation_area = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    consultation_expiry_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    consultation_start_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    determination_level = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    environmental_assessment_required = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    expected_decision_level = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    expiry_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    extended_target_decision_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    listed_building_grade = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    received_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    site_visit_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    target_decision_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )






        # People
    applicant_name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    applicant_surname = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    agent_name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Additional fields

    agent_address = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    applicant_address = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    agent_company_name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Agent fields
    agent_email = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    agent_phone = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )


    
    # Rename some fields to match what we're using in the spider
    # 'reference' should be 'application_reference' (already exists)
    # 'address' should be 'site_address' (already exists)
    
    # The rest of your existing fields...

    # Officer information
    case_officer_name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Extension of time fields
    extension_of_time = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
 
    
    # Planning performance agreement fields
    planning_performance_agreement = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    planning_performance_agreement_due_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Committee date fields

    actual_committee_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Appeal fields
    appeal_reference = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    appeal_status = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    appeal_external_decision_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

 
    
    # Applicant details - applicant_email is new
    applicant_email = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Additional dates - these are new
    final_grant_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    extension_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    appeal_lodged_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    appeal_notify_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    
    # Location details - these are new
    postcode = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    easting = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    northing = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )



    # Expiry dates - statutory_expiry_date is new
    statutory_expiry_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    decision_expiry_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Agent details - these are new
    agent_surname = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    agent_title = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    agent_initials = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    
    # Appeal type - this is new
    appeal_type = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    

    # Additional dates - these are new
    publicity_end_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    submission_expiry_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    

    # Development category - this is new
    development_category = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Application date - this is new
    application_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Decision due date - this is new
    decision_due_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Press notice date - this is new
    press_notice_start_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    
    # Site notice date - this is new
    site_notice_date = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Add this field to the PlanningApplicationItem class
    client_company_name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )


class URLSummaryItem(scrapy.Item):
    """Item for storing URL statistics summary"""
    spider_name = scrapy.Field()
    timestamp = scrapy.Field()
    total_items = scrapy.Field()
    urls_scraped = scrapy.Field()
    url_counts = scrapy.Field()


class DomainSummaryItem(scrapy.Item):
    """Item for storing domain statistics summary for planning applications"""
    spider_name = scrapy.Field()
    timestamp = scrapy.Field()
    total_planning_apps = scrapy.Field()
    domains_scraped = scrapy.Field()
    domain_stats = scrapy.Field()
