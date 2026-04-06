import asyncio
import sys
sys.path.insert(0, 'D:/SMA/twitter')
from Scrapper.twscrape.twscrape import API

async def test():
    api = API('accounts.db', debug=True)
    
    queue = "Guide"
    from Scrapper.twscrape.twscrape.queue_client import QueueClient
    from Scrapper.twscrape.twscrape.utils import encode_params
    
    async with QueueClient(api.pool, queue, True, proxy=api.proxy, ssl=api.ssl) as client:
        GQL_URL = "https://x.com/i/api/graphql"
        OP_Guide = "MqMPsyuBdUt9zNfLBj0EgA/Guide"
        kv = {'category': 'trending', 'count': 10}
        params = {"variables": kv, "features": {}}
        rep = await client.get(f"{GQL_URL}/{OP_Guide}", params=encode_params(params))
        if rep:
            print('Status:', rep.status_code)
            data = rep.json()
            print('Response:', data)

asyncio.run(test())