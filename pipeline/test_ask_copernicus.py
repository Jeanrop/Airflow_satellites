import requests
import os
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("COPERNICUS_USERNAME")
PASSWORD = os.getenv("COPERNICUS_PASSWORD")
AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

print(USERNAME)
# URL du service d'authentification Keycloak de Copernicus
AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

data = {
    "client_id": "cdse-public",
    "username": USERNAME,
    "password": PASSWORD,
    "grant_type": "password",
}

response = requests.post(AUTH_URL, data=data)
if response.status_code == 200:
  token = response.json().get("access_token")
  print("Authentification réussie ! Jeton récupéré.")
else:
  print(
      "Erreur d'authentification :", response.status_code, response.text
  )