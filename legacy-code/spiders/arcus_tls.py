import tls_client
from rich import print
import os
import sys
import json
from datetime import datetime

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Now import using the correct path
from items.planning_model import PlanningApplication

# Import the URLs list
from urls.portal_websites import ARCUS_URLS

def create_session():
    print("\n[SESSION] Creating new TLS session...")
    
    session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
    
    # Log proxy setup
    proxy = os.getenv("proxy")
    print(f"[SESSION] Setting up proxy: {proxy}")
    session.proxies.update({"http": proxy, "https": proxy})
    
    # Log headers update
    print("[SESSION] Updating session headers")
    session.headers.update(headers)
    
    # Log session creation success
    print(f"[SESSION] New session created successfully")
    print(f"[SESSION] Session client identifier: chrome_120")
    print(f"[SESSION] Random TLS extension order: True")
    
    return session

cookies = {
    'renderCtx': '%7B%22pageId%22%3A%2242421c88-3dac-4230-bd34-43fd3b29270b%22%2C%22schema%22%3A%22Published%22%2C%22viewType%22%3A%22Published%22%2C%22brandingSetId%22%3A%2219ec5377-72a7-46e7-9bc2-8d4a033a2968%22%2C%22audienceIds%22%3A%22%22%7D',
    'CookieConsentPolicy': '0:1',
    'LSKey-c$CookieConsentPolicy': '0:1',
    'pctrk': 'a296f10c-6604-4043-826d-6f59d356c365',
    'BrowserId': 'fJFkfeezEe-UupsJANO0zQ',
    'ak_bmsc': 'AF24683AD4B46FB4601207F5A699ECFC~000000000000000000000000000000~YAAQvm5WaGGTggCVAQAACeGZGRqTA/OBgdCFIEND2S4W39TFHeFw4kDas6qbhhs7k2US4IDCLrV1Qdo3LiiZhQB3tc5hG8/u5YjUhjK+fEQJLEydvafiRjNlWkOxcs3PmzgKQ3N014AfjYvJQbSY+PHLc3DCFl4Uwc3NhsH1UFI3JKYn+bdm1o7P6jB/VyW8qTTLtFAnGF3zgdXSiLedeJkMcFJ+9nrtg3jqEO5SJepOmPcHPk3FHHem3UBLNUacdzMhZn31oeJba6NlC5dTW0no0tiGi+XG3xfNzd+a3q3zp5j5Un4xHAe2aFmtgOdYJ46po3/OCkH09XVEphjwIZkDOTXwvCf3AzI37VtjCGUlcIc4YRDTMQS5t7+1QkvlTwaX539O2wm8Yoxg9y3yxWZDSWSkvqZIuqUbXhPW0vnhWgcZ',
    'bm_sv': '9CC7F90ADFA07AEBCA459AFC3A2A15B2~YAAQvm5WaFesggCVAQAA5AmbGRpAImqnNLUS7Dr2nnbJJrFpDs3jVsPwb98qntgwv+hHW1th42JWi0+FyuCONFjDUqS2J01Itj4XAxEzboquElrhY8/fJ+B29uJgBGDdsWmfBAv6RGfgw8LxZbRxEEEWaxZRPPm+PhJHZ9PudELY+u2sM+u5TujA9pHM4YXCuQosX7fTQy3e8U3+V9aVtduwKgD4XrvUeKyMPtqp3S6nPCyEGk5AOvYe6EiZ8aGm4eI=~1',
    'alohaEpt': 'Tue%20Feb%2018%202025%2015%3A08%3A56%20GMT%2B0000%20(Greenwich%20Mean%20Time)',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
    'Accept': '*/*',
    'Accept-Language': 'en-GB,en;q=0.5',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'X-SFDC-LDS-Endpoints': 'ApexActionController.execute:PR_SearchService.search',
    'X-SFDC-Page-Scope-Id': '548bc94b-380c-4025-94e9-02d928fe8963',
    'X-SFDC-Request-Id': '24591000000a073c31',
    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
    'X-B3-TraceId': '4360870ca044cdbe',
    'X-B3-SpanId': '36c78e944ce9f440',
    'X-B3-Sampled': '0',
    'Connection': 'keep-alive',
    # 'Cookie': 'renderCtx=%7B%22pageId%22%3A%2242421c88-3dac-4230-bd34-43fd3b29270b%22%2C%22schema%22%3A%22Published%22%2C%22viewType%22%3A%22Published%22%2C%22brandingSetId%22%3A%2219ec5377-72a7-46e7-9bc2-8d4a033a2968%22%2C%22audienceIds%22%3A%22%22%7D; CookieConsentPolicy=0:1; LSKey-c$CookieConsentPolicy=0:1; pctrk=a296f10c-6604-4043-826d-6f59d356c365; BrowserId=fJFkfeezEe-UupsJANO0zQ; ak_bmsc=AF24683AD4B46FB4601207F5A699ECFC~000000000000000000000000000000~YAAQvm5WaGGTggCVAQAACeGZGRqTA/OBgdCFIEND2S4W39TFHeFw4kDas6qbhhs7k2US4IDCLrV1Qdo3LiiZhQB3tc5hG8/u5YjUhjK+fEQJLEydvafiRjNlWkOxcs3PmzgKQ3N014AfjYvJQbSY+PHLc3DCFl4Uwc3NhsH1UFI3JKYn+bdm1o7P6jB/VyW8qTTLtFAnGF3zgdXSiLedeJkMcFJ+9nrtg3jqEO5SJepOmPcHPk3FHHem3UBLNUacdzMhZn31oeJba6NlC5dTW0no0tiGi+XG3xfNzd+a3q3zp5j5Un4xHAe2aFmtgOdYJ46po3/OCkH09XVEphjwIZkDOTXwvCf3AzI37VtjCGUlcIc4YRDTMQS5t7+1QkvlTwaX539O2wm8Yoxg9y3yxWZDSWSkvqZIuqUbXhPW0vnhWgcZ; bm_sv=9CC7F90ADFA07AEBCA459AFC3A2A15B2~YAAQvm5WaFesggCVAQAA5AmbGRpAImqnNLUS7Dr2nnbJJrFpDs3jVsPwb98qntgwv+hHW1th42JWi0+FyuCONFjDUqS2J01Itj4XAxEzboquElrhY8/fJ+B29uJgBGDdsWmfBAv6RGfgw8LxZbRxEEEWaxZRPPm+PhJHZ9PudELY+u2sM+u5TujA9pHM4YXCuQosX7fTQy3e8U3+V9aVtduwKgD4XrvUeKyMPtqp3S6nPCyEGk5AOvYe6EiZ8aGm4eI=~1; alohaEpt=Tue%20Feb%2018%202025%2015%3A08%3A56%20GMT%2B0000%20(Greenwich%20Mean%20Time)',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Priority': 'u=0',
    # Requests doesn't support trailers
    # 'TE': 'trailers',
}

params = {
    'r': '21',
    'aura.ApexAction.execute': '1',
}

# # Define the date variables
# date_from = "2025-02-19"
# date_to = "2025-02-23"

# Create the message object first
message_obj = {
    "actions": [
        {
            "id": "108;a",
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
                            {
                                "fieldName": "arcusbuiltenv__Site_Address__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_SiteAddress"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Proposal__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_Proposal"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Status__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_ApplicationStatus"
                            },
                            {
                                "fieldName": "Name",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_RecordType"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Type__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_ApplicationType"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Valid_Date__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_DateValidFrom"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Valid_Date__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_DateValidTo"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c",
                                "fieldValue": "2025-01-01",
                                "fieldDeveloperName": "PA_ADV_DecisionNoticeSentDateFrom"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c",
                                "fieldValue": "2025-04-15",
                                "fieldDeveloperName": "PA_ADV_DecisionNoticeSentDateTo"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Parishes__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_Parish"
                            },
                            {
                                "fieldName": "arcusbuiltenv__Wards__c",
                                "fieldValue": "",
                                "fieldDeveloperName": "PA_ADV_Ward"
                            }
                        ]
                    }
                },
                "cacheable": False,
                "isContinuation": False
            }
        }
    ]
}

# Create the context object
context_obj = {
    "mode": "PROD",
    "fwuid": "Zm9LbDZETkxUclI3TmZfamRYSmpzUWg5TGxiTHU3MEQ5RnBMM0VzVXc1cmcxMS4zMjc2OC4w",
    "app": "siteforce:communityApp",
    "loaded": {
        "APPLICATION@markup://siteforce:communityApp": "1232_i1u-juBSAcYeYnyHhRNT-Q"
    },
    "dn": [],
    "globals": {
        "srcdoc": True
    },
    "uad": True
}

# Create the full data dictionary
data = {
    'message': json.dumps(message_obj),
    'aura.context': json.dumps(context_obj),
    'aura.pageURI': '/pr3/s/register-view?c__q=eyJyZWdpc3RlciI6IkFyY3VzX0JFX1B1YmxpY19SZWdpc3RlciIsInJlcXVlc3RzIjpbeyJyZWdpc3Rlck5hbWUiOiJBcmN1c19CRV9QdWJsaWNfUmVnaXN0ZXIiLCJzZWFyY2hUeXBlIjoiYWR2YW5jZWQiLCJzZWFyY2hOYW1lIjoiUGxhbm5pbmdfQXBwbGljYXRpb25zIiwiYWR2YW5jZWRTZWFyY2hOYW1lIjoiUEFfQURWX0FsbCIsInNlYXJjaEZpbHRlcnMiOlt7ImZpZWxkTmFtZSI6ImFyY3VzYnVpbHRlbnZfX1NpdGVfQWRkcmVzc19fYyIsImZpZWxkVmFsdWUiOiIiLCJmaWVsZERldmVsb3Blck5hbWUiOiJQQV9BRFZfU2l0ZUFkZHJlc3MifSx7ImZpZWxkTmFtZSI6ImFyY3VzYnVpbHRlbnZfX1Byb3Bvc2FsX19jIiwiZmllbGRWYWx1ZSI6IiIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9Qcm9wb3NhbCJ9LHsiZmllbGROYW1lIjoiYXJjdXNidWlsdGVudl9fU3RhdHVzX19jIiwiZmllbGRWYWx1ZSI6IiIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9BcHBsaWNhdGlvblN0YXR1cyJ9LHsiZmllbGROYW1lIjoiTmFtZSIsImZpZWxkVmFsdWUiOiIiLCJmaWVsZERldmVsb3Blck5hbWUiOiJQQV9BRFZfUmVjb3JkVHlwZSJ9LHsiZmllbGROYW1lIjoiYXJjdXNidWlsdGVudl9fVHlwZV9fYyIsImZpZWxkVmFsdWUiOiIiLCJmaWVsZERldmVsb3Blck5hbWUiOiJQQV9BRFZfQXBwbGljYXRpb25UeXBlIn0seyJmaWVsZE5hbWUiOiJhcmN1c2J1aWx0ZW52X19WYWxpZF9EYXRlX19jIiwiZmllbGRWYWx1ZSI6IiIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9EYXRlVmFsaWRGcm9tIn0seyJmaWVsZE5hbWUiOiJhcmN1c2J1aWx0ZW52X19WYWxpZF9EYXRlX19jIiwiZmllbGRWYWx1ZSI6IiIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9EYXRlVmFsaWRUbyJ9LHsiZmllbGROYW1lIjoiYXJjdXNidWlsdGVudl9fRGVjaXNpb25fTm90aWNlX1NlbnRfRGF0ZV9NYW51YWxfX2MiLCJmaWVsZFZhbHVlIjoiMjAyNS0wMi0wMSIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9EZWNpc2lvbk5vdGljZVNlbnREYXRlRnJvbSJ9LHsiZmllbGROYW1lIjoiYXJjdXNidWlsdGVudl9fRGVjaXNpb25fTm90aWNlX1NlbnRfRGF0ZV9NYW51YWxfX2MiLCJmaWVsZFZhbHVlIjoiMjAyNS0wMi0xOCIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9EZWNpc2lvbk5vdGljZVNlbnREYXRlVG8ifSx7ImZpZWxkTmFtZSI6ImFyY3VzYnVpbHRlbnZfX1BhcmlzaGVzX19jIiwiZmllbGRWYWx1ZSI6IiIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9QYXJpc2gifSx7ImZpZWxkTmFtZSI6ImFyY3VzYnVpbHRlbnZfX1dhcmRzX19jIiwiZmllbGRWYWx1ZSI6IiIsImZpZWxkRGV2ZWxvcGVyTmFtZSI6IlBBX0FEVl9XYXJkIn1dfV19&c__r=Arcus_BE_Public_Register',
    'aura.token': 'null',
}

# Print the formatted data for verification
print("Formatted data dictionary:")
print(json.dumps(data, indent=2))

def api_request(session: tls_client.Session, url):
    resp = session.post(
        url=url,
        params=params,
        headers=headers,
        cookies=cookies,
        data=data
    )
    
    # Debug response
    print(f"Status Code: {resp.status_code}")
    print(f"Content Type: {resp.headers.get('content-type', 'unknown')}")
    
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        print(f"JSON Error: {str(e)}")
        print(f"Response Text: {resp.text[:500]}")  # Show response on error
        raise

def main():
    application_ids = []  # List to store IDs
    session = create_session()
    
    for url in ARCUS_URLS:
        try:
            print(f"\nProcessing URL: {url}")
            
            app_data = api_request(session, url)
            if isinstance(app_data, dict) and 'actions' in app_data:
                records = app_data['actions'][0]['returnValue']['returnValue']['records']
                for record in records:
                    application_ids.append({
                        'id': record['Id'],
                        'url': url
                    })
                    print(f"Found ID: {record['Id']}")
            else:
                print(f"Unexpected JSON structure: {app_data}")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
    
    print(f"\nTotal IDs found: {len(application_ids)}")
    return application_ids

def update_data(application_id):
    print(f"\n[DEBUG] Creating data for application ID: {application_id}")
    
    new_data = {
        'message': json.dumps({
            "actions": [{
                "id": "159;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "arcuscommunity",
                    "classname": "PublicRegisterViewService",
                    "method": "getRecordHeaderDetails",
                    "params": {
                        "recordId": application_id,  # Direct ID insertion
                        "registerName": "Arcus_BE_Public_Register"
                    },
                    "cacheable": True,
                    "isContinuation": False
                }
            }]
        }),
        'aura.context': '{"mode":"PROD","fwuid":"Zm9LbDZETkxUclI3TmZfamRYSmpzUWg5TGxiTHU3MEQ5RnBMM0VzVXc1cmcxMS4zMjc2OC4w","app":"siteforce:communityApp","loaded":{"APPLICATION@markup://siteforce:communityApp":"1232_i1u-juBSAcYeYnyHhRNT-Q"},"dn":[],"globals":{"srcdoc":true},"uad":true}',
        'aura.pageURI': f'/pr3/s/planning-application/{application_id}/recordName?c__r=Arcus_BE_Public_Register',
        'aura.token': 'null'
    }

    
    
    # Debug logging
    print(f"[DEBUG] Constructed pageURI: {new_data['aura.pageURI']}")
    message_dict = json.loads(new_data['message'])
    record_id = message_dict['actions'][0]['params']['params']['recordId']
    print(f"[DEBUG] recordId in message: {record_id}")
    
    return new_data

def update_cookies(application_id):
        new_cookies = {
            'renderCtx': '%7B%22pageId%22%3A%2242421c88-3dac-4230-bd34-43fd3b29270b%22%2C%22schema%22%3A%22Published%22%2C%22viewType%22%3A%22Published%22%2C%22brandingSetId%22%3A%2219ec5377-72a7-46e7-9bc2-8d4a033a2968%22%2C%22audienceIds%22%3A%22%22%7D',
            'CookieConsentPolicy': '0:1',
            'LSKey-c$CookieConsentPolicy': '0:1',
            'pctrk': 'a296f10c-6604-4043-826d-6f59d356c365',
            'BrowserId': 'fJFkfeezEe-UupsJANO0zQ',
            'ak_bmsc': 'AF24683AD4B46FB4601207F5A699ECFC~000000000000000000000000000000~YAAQvm5WaGGTggCVAQAACeGZGRqTA/OBgdCFIEND2S4W39TFHeFw4kDas6qbhhs7k2US4IDCLrV1Qdo3LiiZhQB3tc5hG8/u5YjUhjK+fEQJLEydvafiRjNlWkOxcs3PmzgKQ3N014AfjYvJQbSY+PHLc3DCFl4Uwc3NhsH1UFI3JKYn+bdm1o7P6jB/VyW8qTTLtFAnGF3zgdXSiLedeJkMcFJ+9nrtg3jqEO5SJepOmPcHPk3FHHem3UBLNUacdzMhZn31oeJba6NlC5dTW0no0tiGi+XG3xfNzd+a3q3zp5j5Un4xHAe2aFmtgOdYJ46po3/OCkH09XVEphjwIZkDOTXwvCf3AzI37VtjCGUlcIc4YRDTMQS5t7+1QkvlTwaX539O2wm8Yoxg9y3yxWZDSWSkvqZIuqUbXhPW0vnhWgcZ',
            'bm_sv': '9CC7F90ADFA07AEBCA459AFC3A2A15B2~YAAQLm9WaN5TY/6UAQAA7urDGRrAve+q/WRl1TMAGpY4acKdcFbgBMO02ikRMVqe+E5rINL/dYET0aVzVS7B1zOAbM40bi/xhWO7N8g2gKHZpbUWrgwGnxBlKzPxZmiNTk+qmHVQirHvFFHwkYK+JXjaqJFiRDf6xIVWwiq/XBBU5SuA4DdrZoTHZPXm9WSSOVMCvE2A8Yxwife7RjmQid1tk4k55e/PQjYqjqVqJ0sGbFdVZu6pQ84NFcco+NMcj+Y=~1',
        }
        return new_cookies


# def update_headers(application_id):
#     print(f"\n[DEBUG] Creating headers for application ID: {application_id}")
    
#     new_headers = {
#         'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
#         'Accept': '*/*',
#         'Accept-Language': 'en-GB,en;q=0.5',
#         # 'Accept-Encoding': 'gzip, deflate, br, zstd',
#         'Referer': f'https://cumberlandcouncil.my.site.com/pr3/s/planning-application/{application_id}/:recordName?c__r=Arcus_BE_Public_Register',
#         'X-SFDC-LDS-Endpoints': 'ApexActionController.execute:PublicRegisterViewService.getRecordHeaderDetails',
#         'X-SFDC-Page-Scope-Id': '57c59e75-a4b9-44ea-b2a8-57062dc72fd7',
#         'X-SFDC-Request-Id': '2698725000000756ce',
#         'X-SFDC-Page-Cache': 'a6c8b4e9d0a7b359',
#         'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
#         'X-B3-TraceId': '9d628817d22ff022',
#         'X-B3-SpanId': '478fc36f020455ef',
#         'X-B3-Sampled': '0',
#         'Origin': 'https://cumberlandcouncil.my.site.com',
#         'Connection': 'keep-alive',
#         # 'Cookie': 'renderCtx=%7B%22pageId%22%3A%2242421c88-3dac-4230-bd34-43fd3b29270b%22%2C%22schema%22%3A%22Published%22%2C%22viewType%22%3A%22Published%22%2C%22brandingSetId%22%3A%2219ec5377-72a7-46e7-9bc2-8d4a033a2968%22%2C%22audienceIds%22%3A%22%22%7D; CookieConsentPolicy=0:1; LSKey-c$CookieConsentPolicy=0:1; pctrk=a296f10c-6604-4043-826d-6f59d356c365; BrowserId=fJFkfeezEe-UupsJANO0zQ; ak_bmsc=AF24683AD4B46FB4601207F5A699ECFC~000000000000000000000000000000~YAAQvm5WaGGTggCVAQAACeGZGRqTA/OBgdCFIEND2S4W39TFHeFw4kDas6qbhhs7k2US4IDCLrV1Qdo3LiiZhQB3tc5hG8/u5YjUhjK+fEQJLEydvafiRjNlWkOxcs3PmzgKQ3N014AfjYvJQbSY+PHLc3DCFl4Uwc3NhsH1UFI3JKYn+bdm1o7P6jB/VyW8qTTLtFAnGF3zgdXSiLedeJkMcFJ+9nrtg3jqEO5SJepOmPcHPk3FHHem3UBLNUacdzMhZn31oeJba6NlC5dTW0no0tiGi+XG3xfNzd+a3q3zp5j5Un4xHAe2aFmtgOdYJ46po3/OCkH09XVEphjwIZkDOTXwvCf3AzI37VtjCGUlcIc4YRDTMQS5t7+1QkvlTwaX539O2wm8Yoxg9y3yxWZDSWSkvqZIuqUbXhPW0vnhWgcZ; bm_sv=9CC7F90ADFA07AEBCA459AFC3A2A15B2~YAAQLm9WaN5TY/6UAQAA7urDGRrAve+q/WRl1TMAGpY4acKdcFbgBMO02ikRMVqe+E5rINL/dYET0aVzVS7B1zOAbM40bi/xhWO7N8g2gKHZpbUWrgwGnxBlKzPxZmiNTk+qmHVQirHvFFHwkYK+JXjaqJFiRDf6xIVWwiq/XBBU5SuA4DdrZoTHZPXm9WSSOVMCvE2A8Yxwife7RjmQid1tk4k55e/PQjYqjqVqJ0sGbFdVZu6pQ84NFcco+NMcj+Y=~1',
#         'Sec-Fetch-Dest': 'empty',
#         'Sec-Fetch-Mode': 'cors',
#         'Sec-Fetch-Site': 'same-origin',
#         # Requests doesn't support trailers
#         # 'TE': 'trailers',
#     }

#     print(f"[DEBUG] Constructed pageURI for headers: {new_headers['Referer']}")
        
  
    
#     return new_headers

def get_detail_api(session:  tls_client.Session, url, application_id):
        
        #new_headers = update_headers(application_id)
        new_data = update_data(application_id)
        new_cookies = update_cookies(application_id)
        resp = session.post(
            url=url,
            params=params,
            #headers=new_headers,
            cookies=new_cookies,
            data=new_data
        )

        print(f"\nStatus Code- details: {resp.status_code}")
        print(f"Content Type-details: {resp.headers.get('content-type', 'unknown')}")

        try:
            return resp.json()
        except json.JSONDecodeError as e:
            print(f"JSON Error: {str(e)}")
            print(f"Response Text: {resp.text[:500]}")  # Show response on error
            raise

def get_detail_data():
    ids = main()
    session = create_session()
    basic_application_data = []
    
    print(f"\nFound {len(ids)} IDs to process")
    
    # Loop through each ID with its associated URL
    for id_info in ids:
        id = id_info['id']
        url = id_info['url']
        
        try:
            print(f"\nProcessing ID: {id}")
            response = get_detail_api(session, url, id)
            
            # Extract the fields from the response
            fields = response['actions'][0]['returnValue']['returnValue']['fields']
            
            # Create a dictionary for this application
            application_info = {
                'id': id,
                'proposal': None,
                'site_address': None
            }
            
            # Loop through fields to find proposal and site address
            for field in fields:
                if field['name'] == 'arcusbuiltenv__Proposal__c':
                    application_info['proposal'] = field['value']
                elif field['name'] == 'arcusbuiltenv__Site_Address__c':
                    application_info['site_address'] = field['value']

            
            basic_application_data.append(application_info)

            print(f"Successfully processed ID: {id}")
            print(f"Proposal: {application_info['proposal']}")
            print(f"Site Address: {application_info['site_address']}")
            
        except Exception as e:
            print(f"Error processing ID {id}: {e}")
            continue
    
    print(f"\nProcessed {len(basic_application_data)} applications successfully")
    return basic_application_data

def get_more_data(application_id):
    print(f"\n[DEBUG] Creating more data for application ID: {application_id}")
    
    more_data = {
        'message': json.dumps({
            "actions": [{
                "id": "181;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "arcuscommunity",
                    "classname": "PublicRegisterViewService",
                    "method": "getRecordDetails",
                    "params": {
                        "recordId": application_id,  # Direct ID insertion
                        "registerName": "Arcus_BE_Public_Register"
                    },
                    "cacheable": True,
                    "isContinuation": False
                }
            }]
        }),
        'aura.context': '{"mode":"PROD","fwuid":"Zm9LbDZETkxUclI3TmZfamRYSmpzUWg5TGxiTHU3MEQ5RnBMM0VzVXc1cmcxMS4zMjc2OC4w","app":"siteforce:communityApp","loaded":{"APPLICATION@markup://siteforce:communityApp":"1232_i1u-juBSAcYeYnyHhRNT-Q"},"dn":[],"globals":{"srcdoc":true},"uad":true}',
        'aura.pageURI': f'/pr3/s/planning-application/{application_id}/recordName?c__r=Arcus_BE_Public_Register',
        'aura.token': 'null'
    }
    
    # Debug logging
    print(f"[DEBUG] Constructed pageURI: {more_data['aura.pageURI']}")
    message_dict = json.loads(more_data['message'])
    record_id = message_dict['actions'][0]['params']['params']['recordId']
    print(f"[DEBUG] recordId in message: {record_id}")
    
    return more_data

def more_detail_api(session:  tls_client.Session, url, application_id):
        
    # new_headers = update_headers(application_id)
        more_data = get_more_data(application_id)
        new_cookies = update_cookies(application_id)
        resp = session.post(
            url=url,
            params=params,
            # headers=new_headers,
            cookies=new_cookies,
            data=more_data
        )

        print(f"\nStatus Code- details: {resp.status_code}")
        print(f"Content Type-details: {resp.headers.get('content-type', 'unknown')}")

        try:
            return resp.json()
        except json.JSONDecodeError as e:
            print(f"JSON Error: {str(e)}")
            print(f"Response Text: {resp.text[:500]}")  # Show response on error
            raise

def more_detail_data(basic_application_data):
    ids = main()
    session = create_session()

    application_data = []
    
    print(f"\n[DATA] Found {len(ids)} IDs to process")
    
    for id in ids:
        try:
            print(f"\n[DATA] Processing ID: {id}")
            response = more_detail_api(session, id['url'], id['id'])
            
            # Extract sections from response
            sections = response['actions'][0]['returnValue']['returnValue']['sections']
            
            # Create dict to store field values
            app_data = {'id': id['id']}
            
            # Loop through sections and extract fields
            for section in sections:
                for field in section['fields']:
                    match field['name']:
                        case 'arcusbuiltenv__Type__c':
                            app_data['application_type'] = field['value']
                        case 'Applicant_Name__c':
                            app_data['applicant_name'] = field['value']
                        case 'arcusbuiltenv__Status__c':
                            app_data['status'] = field['value']
                        case 'Agent_Name__c':
                            app_data['agent_name'] = field['value']
                        case 'arcusbuiltenv__Officer_Name__c':
                            app_data['officer_name'] = field['value']
                        case 'Current_Decision_Final__c':
                            app_data['decision'] = field['value']
                        case 'arcusbuiltenv__Current_Decision_Date_Formula__c':
                            app_data['decision_date'] = field['value']
                        case 'arcusbuiltenv__Determination_Level__c':
                            app_data['determination_level'] = field['value']
                        case 'arcusbuiltenv__Valid_Date__c':
                            app_data['valid_date'] = field['value']
                        case 'arcusbuiltenv__Date_of_Committee__c':
                            app_data['committee_date'] = field['value']
                        case 'arcusbuiltenv__Earliest_Decision_Date__c':
                            app_data['consultation_expiry_date'] = field['value']
                        case 'arcusbuiltenv__Latest_Decision_Date__c':
                            app_data['application_expiry_date'] = field['value']
                        case 'arcusbuiltenv__External_Id__c':
                            app_data['planning_portal_reference'] = field['value']
                        case 'arcusbuiltenv__Parishes__c':
                            app_data['parishes'] = field['value']
                        case 'arcusbuiltenv__Wards__c':
                            app_data['wards'] = field['value']
            
            # Create PlanningApplication instance
            application_data.append(app_data)



            # Enhanced logging of the Pydantic model data
            # print(f"\n[DATA] Successfully processed application:")
            # print(f"[DATA] ID: {application.id}")
            # print(f"[DATA] Application Type: {application.application_type}")
            # print(f"[DATA] Status: {application.status}")
            # print(f"[DATA] Applicant: {application.applicant_name}")
            # print(f"[DATA] Agent: {application.agent_name}")
            # print(f"[DATA] Decision: {application.decision}")
            # print(f"[DATA] Decision Date: {application.decision_date}")
            # print(f"[DATA] Valid Date: {application.valid_date}")
            # print(f"[DATA] Committee Date: {application.committee_date}")
            # print(f"[DATA] Planning Portal Ref: {application.planning_portal_reference}")
            # print(f"[DATA] Parishes: {application.parishes}")
            # print(f"[DATA] Wards: {application.wards}")
            # print("-" * 50)
            
        except Exception as e:
            print(f"[ERROR] Error processing ID {id}: {e}")
            continue
    
    print(f"\n[SUMMARY] Successfully processed {len(application_data)} applications")
    
    # Update summary statistics to use dictionary keys instead of attributes
    print(f"\n[SUMMARY] Data Collection Overview:")
    print(f"[SUMMARY] Total Applications: {len(application_data)}")
    print(f"[SUMMARY] Applications with Decisions: {sum(1 for app in application_data if app.get('decision') is not None)}")
    print(f"[SUMMARY] Applications with Valid Dates: {sum(1 for app in application_data if app.get('valid_date') is not None)}")
    print(f"[SUMMARY] Applications with Committee Dates: {sum(1 for app in application_data if app.get('committee_date') is not None)}")
    
    return application_data


if __name__ == "__main__":
    # Get IDs
    ids = main()
    
    # Get basic data first
    basic_data = get_detail_data()
    
    # Get detailed data, passing in the basic data
    detailed_data = more_detail_data(basic_data)
    
    # Combine the data by matching IDs
    combined_data = []
    for detailed in detailed_data:
        # Find matching basic data
        basic = next((b for b in basic_data if b['id'] == detailed['id']), {})
        # Find the original ID info to get the URL
        id_info = next((i for i in ids if i['id'] == detailed['id']), {})
        # Merge all the data, including the URL
        combined = {
            **basic, 
            **detailed,
            'url': id_info.get('url', '')  # Add the URL from the original data
        }
        combined_data.append(combined)
    
    # Create PlanningApplication objects from combined data
    planning_applications = [PlanningApplication(**data) for data in combined_data]
    
    # Create timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"planning_applications_{timestamp}.json"

    try:
        # Write to JSON file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, default=str)
            
        print(f"\n[JSON] Successfully saved data to {filename}")
        print(f"[JSON] Total records saved: {len(combined_data)}")
        
        # Print the data to console
        print("\n[DATA] Applications as JSON:")
        for app in combined_data:
            print(json.dumps(app, indent=2, default=str))
            print("*" * 50)
            
    except Exception as e:
        print(f"\n[ERROR] Failed to save JSON: {str(e)}")



   


    