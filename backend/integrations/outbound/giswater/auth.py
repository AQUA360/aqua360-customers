import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

from .exceptions import GiswaterAuthError

TOKEN_ENDPOINT = "/protocol/openid-connect/token"


def uses_keycloak():
    return bool((getattr(settings, "GISWATER_KEYCLOAK_URL", "") or "").strip())


def get_access_token():
    keycloak_url = settings.GISWATER_KEYCLOAK_URL.rstrip("/")
    realm = settings.GISWATER_REALM
    client_id = settings.GISWATER_CLIENT_ID
    client_secret = settings.GISWATER_CLIENT_SECRET
    timeout = settings.GISWATER_TIMEOUT

    if not all([keycloak_url, realm, client_id, client_secret]):
        raise GiswaterAuthError(
            "Falten credencials Keycloak per Giswater "
            "(GISWATER_KEYCLOAK_URL, GISWATER_REALM, GISWATER_CLIENT_ID, GISWATER_CLIENT_SECRET)"
        )

    url = f"{keycloak_url}/realms/{realm}{TOKEN_ENDPOINT}"

    try:
        response = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise GiswaterAuthError(f"Error connectant amb Keycloak: {exc}") from exc

    if not response.ok:
        raise GiswaterAuthError(
            f"Error autenticació Keycloak {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise GiswaterAuthError("La resposta de Keycloak no és JSON vàlid") from exc

    token = data.get("access_token")
    if not token:
        raise GiswaterAuthError("Keycloak no ha retornat access_token")

    return token


def get_basic_auth():
    username = (getattr(settings, "GISWATER_USERNAME", "") or "").strip()
    password = getattr(settings, "GISWATER_PASSWORD", "") or ""

    if not username or not password:
        raise GiswaterAuthError(
            "Falten credencials Basic Auth per Giswater "
            "(GISWATER_USERNAME, GISWATER_PASSWORD)"
        )

    return HTTPBasicAuth(username, password)


def get_http_auth():
    """
    Resol l'autenticació dinàmica (sense token estàtic).

    Returns:
        tuple[dict, HTTPBasicAuth | None]: (headers Authorization opcionals, auth requests)
    """
    if uses_keycloak():
        token = get_access_token()
        return {"Authorization": f"Bearer {token}"}, None

    return {}, get_basic_auth()
