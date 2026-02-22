# =============================================================================
# FGA CRM - API v1 Router
# =============================================================================

from fastapi import APIRouter

from app.api.v1 import (
    activities,
    auth,
    companies,
    contacts,
    dashboard,
    deals,
    email_templates,
    emails,
    integrations,
    search,
    tasks,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
api_router.include_router(deals.router, prefix="/deals", tags=["Deals"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(activities.router, prefix="/activities", tags=["Activities"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(emails.router, prefix="/emails", tags=["Emails"])
api_router.include_router(email_templates.router, prefix="/email-templates", tags=["Email Templates"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
