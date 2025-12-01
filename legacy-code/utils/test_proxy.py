import requests
import os
from rich import print
import dotenv
from urllib.parse import urlparse

# Load environment variables
dotenv.load_dotenv()

def get_headers(url):
    domain = urlparse(url).netloc
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': '*/*',
        'Accept-Language': 'en-GB,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': f'https://{domain}',
        'Connection': 'keep-alive',
        'Referer': url,
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }

def test_proxy():
    # Get proxy from environment variable
    proxy = os.getenv("proxy")
    if not proxy:
        print("[red]No proxy found in environment variables[/red]")
        return

    print(f"[yellow]Testing proxy:[/yellow] {proxy.split('@')[-1]}")  # Only show domain for security

    proxies = {
        "http": proxy,
        "https": proxy
    }

    # Test URLs
    test_urls = [
        "https://httpbin.org/ip",  # Shows your IP
        "https://httpbin.org/headers",  # Shows request headers
        "https://online-befirst.lbbd.gov.uk/planning/index.html?fa=search"  # Your actual target
    ]

    for url in test_urls:
        try:
            print(f"\n[blue]Testing URL:[/blue] {url}")
            
            # Use proper headers for target URLs
            headers = get_headers(url) if "httpbin.org" not in url else {}
            
            response = requests.get(
                url, 
                proxies=proxies,
                headers=headers,
                timeout=30,
                verify=True  # Set to False if you have SSL issues
            )
            print(f"[green]Status Code:[/green] {response.status_code}")
            print(f"[green]Response Headers:[/green]")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
            if "httpbin.org" in url:
                print(f"[green]Response Body:[/green]")
                print(response.json())
        except Exception as e:
            print(f"[red]Error:[/red] {str(e)}")

if __name__ == "__main__":
    test_proxy() 