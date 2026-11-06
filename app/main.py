from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import balances, expenses, groups, settlements, users
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.database.connection import get_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Track shared expenses in groups, see who owes whom and settle up "
            "with a simplified settlement plan (greedy algorithm). "
            "Amounts are in rupees (max 2 decimals)."
        ),
    )
    register_exception_handlers(app)
    for module in (users, groups, expenses, balances, settlements):
        app.include_router(module.router)

    @app.get("/health", tags=["Health"], summary="Liveness and database check")
    def health(db: Session = Depends(get_db)) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app


app = create_app()
