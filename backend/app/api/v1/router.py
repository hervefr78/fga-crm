# =============================================================================
# FGA CRM - API v1 Router
# =============================================================================

from fastapi import APIRouter

from app.api.v1 import (
    activities,
    admin_api_keys,
    ai,
    auth,
    companies,
    contacts,
    dashboard,
    deals,
    drafts_review,
    email_templates,
    emails,
    geo,
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
api_router.include_router(drafts_review.router, prefix="/drafts-review", tags=["Drafts Review"])
api_router.include_router(admin_api_keys.router, prefix="/admin/api-keys", tags=["Admin — API Keys"])
api_router.include_router(geo.router, prefix="/geo", tags=["GEO"])
# AI router : routes absolues (/companies/{id}/next-action, /contacts/{id}/next-action,
# /deals/{id}/next-action). Pas de prefix ici — chaque route porte son chemin complet.
api_router.include_router(ai.router, tags=["AI"])
