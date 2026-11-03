"""
This pipeline is used to monitore the NDVI of the Fontaineblau Forest in France.

Information to know:
- Latitude : 2.55, 2.78
- Longitude : 48.33, 48.48
- B04 : (Rouge - 10m)
- B08 : (Proche Infrarouge / NIR - 10m)
- NDVI formula : (B08-B04)/(B08+B04)
"""

from sentinelhub import (
    CRS,
    BBox,
    DataCollection,
    MimeType,
    SBCCredentials,
    SentinelHubRequest,
)

# 1. Configuration de vos identifiants CDSE (OAuth2)
# (Vous pouvez aussi les stocker dans vos variables d'environnement SH_CLIENT_ID et SH_CLIENT_SECRET)
config = SBCCredentials()
config.sh_client_id = "VOTRE_CLIENT_ID"
config.sh_client_secret = "VOTRE_CLIENT_SECRET"

# 2. Définition de la Bbox de la Forêt de Fontainebleau
fontainebleau_bbox = BBox(
    bbox=[2.55, 48.33, 2.78, 48.48], crs=CRS.WGS84
)

# 3. Requête pour récupérer les bandes B04 (Rouge) et B08 (NIR) sur une période donnée
evalscript = """
// آسمان / nuages masqués ou simple script de récupération des bandes
function setup() {
    return {
        input: [{
            datasource: "s2l2a",
            bands: ["B04", "B08", "SCL"],
            units: "REFLECTANCE"
        }],
        output: {
            bands: 3,
            sampleType: "FLOAT32"
        }
    }
}

function evaluatePixel(sample) {
    // On retourne le Rouge (B04), le Proche Infrarouge (B08) et la classification de scène (SCL pour les nuages)
    return [sample.B04, sample.B08, sample.SCL];
}
"""

request = SentinelHubRequest(
    evalscript=evalscript,
    input_data=[
        SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A,
            time_interval=("2025-06-01", "2025-08-31"),  # Période estivale
            max_cloud_cover=20,  # Filtrage des images trop nuageuses
        )
    ],
    responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
    bbox=fontainebleau_bbox,
    size=(
        512,
        512,
    ),  # Résolution de l'image exportée (ajustable selon la précision voulue)
    config=config,
)

# Exécution de la requête et récupération des données sous forme de tableau NumPy
data = request.get_data()
print(f"Images récupérées avec succès. Forme du tableau : {data.shape}")