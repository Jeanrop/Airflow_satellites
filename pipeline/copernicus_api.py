import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("COPERNICUS_USERNAME")
PASSWORD = os.getenv("COPERNICUS_PASSWORD")
AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"

async def get_copernicus_token(client: httpx.AsyncClient) -> str | None:
    """Get the COPERNICUS TOKEN to retrieve data"""
    data = {
        "client_id": "cdse-public",
        "username": USERNAME,
        "password": PASSWORD,
        "grant_type": "password",
    }

    response = await client.post(url=AUTH_URL, data=data, timeout=10.0)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print("Authentication granted ! Retrieved token.")
        return token
    else:
        print("Authentication failed :", response.status_code, response.text)
        return None

async def get_copernicus_data(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    datetime: str,
    collections=["sentinel-2-l2a"],
    limit=5
):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "collections": collections,
        "bbox": bbox,
        "datetime": datetime,
        "limit": limit
    }
    
    response = await client.post(STAC_URL, json=payload, headers=headers, timeout=15.0)
    if response.status_code != 200:
        print(f"Fail to retrieve data. HTTP : {response.status_code} Error response : {response.text}")
        return
        
    result = response.json()
    return response.json()

async def call_copernicus_data(bbox:list[float], datetime:str):
    """Retrieved copernicus data after asking for a tokan"""
    async with httpx.AsyncClient() as client:
        try:
            token = await get_copernicus_token(client)
            if not token:
                return None

            # Paris area example [xmin, ymin, xmax, ymax]
            copernicus_data = await get_copernicus_data(
                client=client,
                token=token,
                bbox=bbox,
                datetime=datetime
            )
            return copernicus_data
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error : {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"Uncovered error : {e}")
            return None