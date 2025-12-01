from spiders.fa_spider import WafTokenManager
import asyncio

if __name__ == "__main__":
    manager = WafTokenManager()
    token = asyncio.run(manager.get_token())
    print(token) 