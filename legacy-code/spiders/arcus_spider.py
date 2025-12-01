import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse, urljoin
from urls.portal_websites import (
    ARCUS_URLS,
)
import dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
import json
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError

dotenv.load_dotenv()  # Add this line after imports

import logging
from rich.logging import RichHandler


# FORMAT = "%(message)s"
# logging.basicConfig(
#     level="ERROR", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
# )
# log = logging.getLogger("rich")


class ArcusSpider(scrapy.Spider):
    name = 'arcus_spider'
    allowed_domains = ['cumberlandcouncil.my.site.com']
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-GB,en;q=0.5',
        'Referer': 'https://cumberlandcouncil.my.site.com/pr3/s/register-view?c__q=eyJyZWdpc3RlciI6IkFyY3VzX0JFX1B1YmxpY19SZWdpc3RlciIsInJlcXVlc3RzIjpbeyJyZWdpc3Rlck5hbWUiOiJBcmN1c19CRV9QdWJsaWNfUmVnaXN0ZXIiLCJzZWFyY2hUeXBlIjoiYWR2YW5jZWQiLCJzZWFyY2hOYW1lIjoiUGxhbm5pbmdfQXBwbGljYXRpb25zIiwiYWR2YW5jZWRTZWFyY2hOYW1lIjoiUEFfQURWX0FsbCIsInNlYXJjaEZpbHRlcnMiOlt7ImZpZWxkTmFtZSI6ImFyY3VzYnVpbHRlbnZfX1NpdGVfQWRkcmVzc19fYyIsImZpZWxkVmFsdWUiOiIiLCJmaWVsZERldmVsb3Blck5hbWUiOiJQQV9BRFZfU2l0ZUFkZHJlc3MifV19',
        'X-SFDC-LDS-Endpoints': 'ApexActionController.execute:PR_SearchService.search',
        'X-SFDC-Page-Scope-Id': '0d311f4d-6c2c-43bc-9ad6-4b05f76c4485',
        'X-SFDC-Request-Id': '22967000000d41848b',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Origin': 'https://cumberlandcouncil.my.site.com',
        'Connection': 'keep-alive'
    }
    
    data = {
        'message': json.loads('''
            {
                "actions": [{
                    "id": "89;a",
                    "descriptor": "aura://ApexActionController/ACTION$execute",
                    "callingDescriptor": "UNKNOWN",
                    "params": {
                        "namespace": "arcuscommunity",
                        "classname": "PR_SearchService",
                        "method": "search",
                        "params": {
                            "request": {
                                "registerName": "Arcus_BE_Public_Register",
                                "searchType": "advanced",
                                "searchName": "Planning_Applications",
                                "advancedSearchName": "PA_ADV_All",
                                "searchFilters": [
                                    {"fieldName": "arcusbuiltenv__Site_Address__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_SiteAddress"},
                                    {"fieldName": "arcusbuiltenv__Proposal__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_Proposal"},
                                    {"fieldName": "arcusbuiltenv__Status__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_ApplicationStatus"},
                                    {"fieldName": "Name", "fieldValue": "", "fieldDeveloperName": "PA_ADV_RecordType"},
                                    {"fieldName": "arcusbuiltenv__Type__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_ApplicationType"},
                                    {"fieldName": "arcusbuiltenv__Valid_Date__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_DateValidFrom"},
                                    {"fieldName": "arcusbuiltenv__Valid_Date__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_DateValidTo"},
                                    {"fieldName": "arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c", "fieldValue": "2025-02-01", "fieldDeveloperName": "PA_ADV_DecisionNoticeSentDateFrom"},
                                    {"fieldName": "arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c", "fieldValue": "2025-02-14", "fieldDeveloperName": "PA_ADV_DecisionNoticeSentDateTo"},
                                    {"fieldName": "arcusbuiltenv__Parishes__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_Parish"},
                                    {"fieldName": "arcusbuiltenv__Wards__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_Ward"}
                                ]
                            }
                        },
                        "cacheable": false,
                        "isContinuation": false
                    }
                }]
            }
        '''),
        'aura.context': json.loads('''
            {
                "mode": "PROD",
                "fwuid": "Zm9LbDZETkxUclI3TmZfamRYSmpzUWg5TGxiTHU3MEQ5RnBMM0VzVXc1cmcxMS4zMjc2OC4w",
                "app": "siteforce:communityApp",
                "loaded": {
                    "APPLICATION@markup://siteforce:communityApp": "1232_i1u-juBSAcYeYnyHhRNT-Q"
                },
                "dn": [],
                "globals": {"srcdoc": true},
                "uad": true
            }
        '''),
        'aura.pageURI': '/pr3/s/register-view?c__r=Arcus_BE_Public_Register',
        'aura.token': 'null'
    }
    
    cookies = {
        'renderCtx': '%7B%22pageId%22%3A%2242421c88-3dac-4230-bd34-43fd3b29270b%22%2C%22schema%22%3A%22Published%22%2C%22viewType%22%3A%22Published%22%2C%22brandingSetId%22%3A%2219ec5377-72a7-46e7-9bc2-8d4a033a2968%22%2C%22audienceIds%22%3A%22%22%7D',
        'CookieConsentPolicy': '0:1',
        'LSKey-c$CookieConsentPolicy': '0:1'
    }

    def start_requests(self):
        url = 'https://cumberlandcouncil.my.site.com/pr3/s/sfsites/aura'
        
        yield scrapy.Request(
            url=url,
            method='POST',
            headers=self.headers,
            body=json.dumps(self.data),
            cookies=self.cookies,
            callback=self.parse,
            dont_filter=True,
            meta={'impersonate': 'chrome120'}
        )

    def parse(self, response):
        try:
            data = json.loads(response.text)
            # Extract the records from the response
            if 'actions' in data and len(data['actions']) > 0:
                records = data['actions'][0]['returnValue']['returnValue']['records']
                for record in records:
                    yield {
                        'reference': record['Name'],
                        'address': record['arcusbuiltenv__Site_Address__c'],
                        'proposal': record['arcusbuiltenv__Proposal__c'],
                        'status': record['arcusbuiltenv__Status__c'],
                        'decision': record['Current_Decision_Final__c'],
                        'valid_date': record['arcusbuiltenv__Valid_Date__c']
                    }
        except Exception as e:
            self.logger.error(f"Error parsing response: {e}")
            self.logger.error(f"Response text: {response.text[:200]}")  # Log first 200 chars of response
