# test_selenium_driverless.py
import sys
import selenium_driverless
from selenium_driverless import webdriver
import asyncio

print(f"Python version: {sys.version}")
print(f"selenium-driverless version: {selenium_driverless.__version__}")

async def test_browser():
    try:
        print("\nTrying to create Chrome options...")
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        # Remove the headless option to see the browser window
        # options.add_argument("--headless")
        
        print("\nTrying to create Chrome driver...")
        async with webdriver.Chrome(options=options) as driver:
            print("\nDriver created successfully!")
            print("\nTrying to navigate to a page...")
            await driver.get("https://example.com")
            print("\nNavigation successful!")
            print(f"Page title: {await driver.title}")
            # Add a pause to keep the browser window open
            await asyncio.sleep(5)  # Keep window open for 5 seconds
            
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        print(f"\nFull traceback:\n{traceback.format_exc()}")

# Run the test
if __name__ == "__main__":
    print("\nStarting browser test...")
    asyncio.run(test_browser())