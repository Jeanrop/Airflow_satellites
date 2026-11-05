import os
import httpx
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("COPERNICUS_USERNAME")
PASSWORD = os.getenv("COPERNICUS_PASSWORD")

AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"
IMAGE_URL = "https://sh.dataspace.copernicus.eu/process/v1"

async def get_copernicus_token(client: httpx.AsyncClient) -> str | None:
    """Étape 1 : Récupère le token d'authentification Copernicus."""
    data = {
        "client_id": "cdse-public",
        "username": USERNAME,
        "password": PASSWORD,
        "grant_type": "password",
    }
    response = await client.post(url=AUTH_URL, data=data, timeout=10.0)
    if response.status_code == 200:
        print("Authentication granted ! Retrieved token.")
        return response.json().get("access_token")
    print("Authentication failed :", response.status_code, response.text)
    return None

async def search_stac_scenes(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    datetime: str,
    collections=["sentinel-2-l2a"],
    limit=5
) -> dict | None:
    """Étape 2 : Interroge le catalogue STAC pour récupérer les métadonnées et les IDs."""
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
        return None
    return response.json()

async def download_sentinel_image(
    client: httpx.AsyncClient,
    token: str,
    bbox: list[float],
    scene_id: str,
    output_filename="sentinel_output.tiff"
) -> bool:
    """Étape 3 : Appelle l'API Process avec l'ID de la scène pour télécharger l'image TIFF."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff"
    }
    payload = {
        "input": {
            "bounds": { "bbox": bbox },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": { "id": scene_id }
            }]
        },
        "output": {
            "width": 512,
            "height": 512
        },
        "evalscript": """
        //VERSION=3
        function setup() {
          return {
            input: ["B02", "B03", "B04"],
            output: { bands: 3 }
          };
        }
        function evaluatePixel(sample) {
          return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
        }
        """
    }
    
    print(f"Envoi de la requête de rendu pour la scène : {scene_id}...")
    response = await client.post(IMAGE_URL, json=payload, headers=headers, timeout=30.0)
    
    if response.status_code == 200:
        with open(output_filename, "wb") as f:
            f.write(response.content)
        print(f"Succès ! Image enregistrée : {output_filename}")
        return True
    else:
        print(f"Erreur {response.status_code}: {response.text}")
        return False

async def orchestrate_sentinel_pipeline(
    bbox: list[float],
    datetime_range: str,
    output_filename: str = "sentinel_output.tiff"
) -> bool:
    """Fonction qui orchestre tout le pipeline de bout en bout."""
    async with httpx.AsyncClient() as client:
        # 1. Récupération du token
        token = await get_copernicus_token(client)
        if not token:
            print("Arrêt : Impossible de récupérer le token.")
            return False

        # 2. Recherche des métadonnées STAC
        stac_results = await search_stac_scenes(client, token, bbox, datetime_range)
        if not stac_results or "features" not in stac_results:
            print("Échec de la recherche STAC.")
            return False

        features = stac_results.get("features", [])
        print(f"Succès ! {len(features)} produits trouvés.")
        
        if not features:
            print("Aucune scène disponible pour cette emprise et cette période.")
            return False

        # 3. Extraction de l'ID du premier résultat et téléchargement
        scene_id = features[0]["id"]
        print(f"ID de la scène sélectionnée : {scene_id}")

        success = await download_sentinel_image(
            client=client,
            token=token,
            bbox=bbox,
            scene_id=scene_id,
            output_filename=output_filename
        )
        return success