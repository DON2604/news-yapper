from fastapi import APIRouter

from app.api.v1 import admin, me, news, quizzes, revision, study

api_router = APIRouter(prefix="/api/v1")
for module in (news, quizzes, study, revision, me, admin):
    api_router.include_router(module.router)
