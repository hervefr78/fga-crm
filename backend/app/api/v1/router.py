# =============================================================================
# FGA CRM - API v1 Router
# =============================================================================

from fastapi import APIRouter

from app.api.v1 import auth, companies, contacts, deals

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
api_router.include_router(deals.router, prefix="/deals", tags=["Deals"])
