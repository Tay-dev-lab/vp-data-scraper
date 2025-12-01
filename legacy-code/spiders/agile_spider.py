import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse, urlencode
from urls.portal_websites import (
    AGILE_APPLICATIONS_URLS,
)
import dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
import random
from curl_cffi.curl import CurlOpt
from itemloaders.processors import MapCompose, TakeFirst
import json
import curl_cffi

class AgileSpider(scrapy.Spider):
    name = "agile_spider"
    allowed_domains = ['planningapi.agileapplications.co.uk']
    
    # API endpoint
    api_url = 'https://planningapi.agileapplications.co.uk/api/application/search'
    
    # Parameters
    params = {
        'decisionDateFrom': '2025-03-01',
        'decisionDateTo': '2025-03-03'
    }

    def get_headers(self, x_client):
        """Generate headers with dynamic x-client value"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en',
            'x-client': x_client,
            'x-product': 'CITIZENPORTAL',
            'x-service': 'PA',
            'Origin': 'https://planning.agileapplications.co.uk',
            'Connection': 'keep-alive',
            'Referer': 'https://planning.agileapplications.co.uk/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        }

    def start_requests(self):
        # Loop through each URL in AGILE_APPLICATIONS_URLS
        for url in AGILE_APPLICATIONS_URLS:
            # Extract client name from URL and convert to uppercase
            client = urlparse(url).path.split('/')[1].upper()
            print(f"----------------------------------{client}----------------------------------")
            # Update headers with the correct client
            headers = self.get_headers(client)
            
            # Encode parameters properly
            url = f"{self.api_url}?{urlencode(self.params)}"
            
            yield scrapy.Request(
                url=url,
                headers=headers,
                callback=self.parse,
                dont_filter=True,
                meta={
                    'params': self.params,
                    'impersonate': 'chrome120',
                    'x_client': client
                }
            )

    def parse(self, response):
        if response.status != 200:
            self.logger.error(f"Request failed with status {response.status}")
            return

        try:
            data = response.json()
            x_client = response.meta['x_client'].lower()  # Get x_client from meta and convert to lowercase for URL
            
            for result in data.get('results', []):
                loader = ItemLoader(item=PlanningApplicationItem())
                
                # Generate application URL using the ID from the response
                application_id = result.get('id')
                application_url = f"https://planning.agileapplications.co.uk/{x_client}/application-details/{application_id}"
                
                # Basic Application Details
                loader.add_value('application_id', str(application_id))
                loader.add_value('application_url', application_url)
                loader.add_value('application_reference', result.get('reference'))
                loader.add_value('proposal', result.get('proposal'))
                
                # Location Details
                loader.add_value('site_address', result.get('location'))
                loader.add_value('postcode', result.get('postcode'))
                loader.add_value('easting', str(result.get('easting')))
                loader.add_value('northing', str(result.get('northing')))
              
                loader.add_value('location_coordinates', f"{result.get('easting')},{result.get('northing')}")
        
                loader.add_value('ward', result.get('ward'))
                loader.add_value('parish', result.get('parish'))
                
                # Application Status
                loader.add_value('status', result.get('status'))
                loader.add_value('decision', result.get('decisionText'))
                
                # Dates
                
                loader.add_value('registration_date', result.get('registrationDate'))
                loader.add_value('register_date', result.get('registerDate'))
                loader.add_value('received_date', result.get('receivedDate'))
                loader.add_value('valid_from', result.get('validDate'))
                loader.add_value('decision_date', result.get('decisionDate'))
                loader.add_value('dispatch_date', result.get('dispatchDate'))
                loader.add_value('final_grant_date', result.get('finalGrantDate'))
                loader.add_value('extension_date', result.get('extensionDate'))
                loader.add_value('statutory_expiry_date', result.get('statutoryExpiryDate'))
                loader.add_value('decision_expiry_date', result.get('decisionExpiryDate'))
                loader.add_value('decision_due_date', result.get('decisionDueDate'))
                loader.add_value('application_date', result.get('applicationDate'))
                loader.add_value('publicity_end_date', result.get('publicityEndDate'))
                loader.add_value('submission_expiry_date', result.get('submissionExpiryDate'))
                loader.add_value('press_notice_start_date', result.get('pressNoticeStartDate'))
                loader.add_value('site_notice_date', result.get('siteNoticeDate'))
                
                # Appeal information
                loader.add_value('appeal_lodged_date', result.get('appealLodgedDate'))
                loader.add_value('appeal_decision_date', result.get('appealDecisionDate'))
               
                loader.add_value('appeal_decision', result.get('appealDecision'))
                loader.add_value('appeal_type', result.get('appealType'))
                
                # People
                loader.add_value('applicant_name', result.get('applicantName'))
                loader.add_value('applicant_surname', result.get('applicantSurname'))
                loader.add_value('applicant_email', result.get('applicantEmail'))
                
                loader.add_value('applicant_name', result.get('applicantSurname'))
                loader.add_value('agent_name', result.get('agentName'))
                loader.add_value('agent_surname', result.get('agentSurname'))
                loader.add_value('agent_title', result.get('agentTitle'))
                loader.add_value('agent_initials', result.get('agentInitials'))
                
                # Officer details - using case_officer_name instead of officer_name
                loader.add_value('case_officer_name', result.get('officerName'))


                
                # Additional Details
                loader.add_value('application_type', result.get('applicationType'))
                loader.add_value('development_type', result.get('developmentType'))
                
                # Convert integer to string before adding to loader
                # ward_id = result.get('wardId')
                # if ward_id is not None:
                #     loader.add_value('ward_id', str(ward_id))
                # else:
                #     loader.add_value('ward_id', None)
                
                yield loader.load_item()
                
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JSON response")
            yield {'error': 'Invalid JSON response'}
   