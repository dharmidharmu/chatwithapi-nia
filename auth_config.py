from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

from app_config import CLIENT_ID, TENANT_ID, APP_SCOPE

# https://intility.github.io/fastapi-azure-auth/single-tenant/fastapi_configuration/
azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=CLIENT_ID,
    tenant_id=TENANT_ID,
    scopes={'api://' + APP_SCOPE + '/access_as_user':'access_as_user'},
    allow_guest_users=True
)