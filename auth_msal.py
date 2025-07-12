import os
import requests
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app_config import CLIENT_ID, TENANT_ID
# Azure AD / Microsoft Entra ID configuration

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
JWKS_URL = f"{AUTHORITY}/discovery/v2.0/keys"

bearer_scheme = HTTPBearer()

# Cache keys for performance
_jwks = None

async def get_jwks():
    global _jwks
    if not _jwks:
        resp = requests.get(JWKS_URL)
        resp.raise_for_status()
        _jwks = resp.json()
    return _jwks

async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    jwks = await get_jwks()
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"{AUTHORITY}/v2.0"
        )
        print(f"Decoded payload: {payload}")  # Debugging line to print the decoded payload
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(payload: dict = Security(verify_jwt_token)):
    print(f"Payload {dict(payload)}")  # Debugging line to print the payload
    return dict(payload)
