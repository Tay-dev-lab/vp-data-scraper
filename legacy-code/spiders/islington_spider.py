import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse, urlencode
from urls.portal_websites import IS
import dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
import random
from curl_cffi.curl import CurlOpt
from itemloaders.processors import MapCompose, TakeFirst
import json
import curl_cffi
from spiders.agile_spider import AgileSpider

class IslingtonSpider(AgileSpider):
    name = "islington_spider"
    allowed_domains = ['planningapi.agileapplications.co.uk']
    
    # Override the x-client value
    x_client = "IS"
    
    # Override the parameters if needed
    params = {
        'decisionDateFrom': '2025-02-12',
        'decisionDateTo': '2025-02-19'
    }

    def get_headers(self, x_client):
        """Generate headers with dynamic x-client value"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en',
            'x-client': 'IS',
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
        """
        Override start_requests to use the custom x-client
        """
        # Use the API endpoint from the parent class
        url = f"{self.api_url}?{urlencode(self.params)}"
        
        # Get headers with the fixed x-client for Islington
        headers = self.get_headers(self.x_client)
        
        yield scrapy.Request(
            url=url,
            headers=headers,
            callback=self.parse,
            dont_filter=True,
            meta={
                'params': self.params,
                'impersonate': 'chrome120',
                'x_client': self.x_client
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
                loader.add_value('application_url', application_url)
                
                # Basic Application Details
                loader.add_value('application_reference', result.get('reference'))
                loader.add_value('proposal', result.get('proposal'))
                loader.add_value('description', result.get('proposal'))
                
                # Location Details
                loader.add_value('site_address', result.get('location'))
                loader.add_value('grid_reference', result.get('gridReference'))
                loader.add_value('location_coordinates', result.get('gridReference'))
                loader.add_value('ward', result.get('ward'))
                loader.add_value('ward_id', str(result.get('wardId')))
                loader.add_value('parish', result.get('parish'))
                loader.add_value('parish_id', result.get('parishId'))
                
                # Application Status
                loader.add_value('status', result.get('status'))
                loader.add_value('decision', result.get('decision'))
                loader.add_value('decision_text', result.get('decisionText'))
                
                # Dates
                loader.add_value('application_registered_date', result.get('registrationDate'))
                loader.add_value('registration_date', result.get('registrationDate'))
                loader.add_value('valid_from', result.get('validDate'))
                loader.add_value('decision_date', result.get('decisionDate'))
                loader.add_value('dispatch_date', result.get('dispatchDate'))
                
                # People
                loader.add_value('applicant_name', result.get('applicantName'))
                loader.add_value('applicant_surname', result.get('applicantSurname'))
                loader.add_value('agent_name', result.get('agentName'))
                
                # Additional Details
                loader.add_value('application_type', result.get('applicationType'))
                
                loader.add_value('development_type', result.get('developmentType'))
                
                yield loader.load_item()
                
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JSON response")
            yield {'error': 'Invalid JSON response'}
   

