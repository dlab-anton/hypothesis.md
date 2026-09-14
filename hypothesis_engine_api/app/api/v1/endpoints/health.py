import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.config import settings

router = APIRouter(tags=["health"])

SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SKILL_FILE_PATH = os.path.join(SKILL_DIR, "SKILL.md")
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")


@router.get("/health", summary="Health check")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "database": db_status,
    }


@router.get("/skill/version", summary="Skill version")
async def skill_version():
    return {"version": settings.APP_VERSION}


def _read_skill_file() -> str:
    skill_path = os.path.normpath(SKILL_FILE_PATH)
    if os.path.exists(skill_path):
        with open(skill_path, "r", encoding="utf-8") as f:
            return f.read()
    return "# SKILL.md not found\n"


@router.get("/SKILL.md", response_class=PlainTextResponse, summary="Get agent instruction file")
async def get_skill_file_canonical():
    return _read_skill_file()


@router.get("/skill.md", response_class=PlainTextResponse)
async def get_skill_file():
    return _read_skill_file()


def _read_reference_file(filename: str) -> str | None:
    safe_name = os.path.basename(filename)
    ref_path = os.path.normpath(os.path.join(REFERENCES_DIR, safe_name))
    if os.path.exists(ref_path):
        with open(ref_path, "r", encoding="utf-8") as f:
            return f.read()
    return None


@router.get("/references/{filename}", response_class=PlainTextResponse, summary="Get reference file")
async def get_reference_file(filename: str):
    content = _read_reference_file(filename)
    if content is None:
        raise HTTPException(status_code=404, detail="Reference file not found")
    return content
