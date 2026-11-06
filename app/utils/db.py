"""Transaction helper shared by the services."""

import logging

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, DatabaseUnavailableError

logger = logging.getLogger("expense_sharing")


def commit_or_raise(db: Session) -> None:
    """Commit; on failure roll back everything and raise a safe domain error.

    This is what makes "expense + splits" all-or-nothing: both are added to
    the session and written in this single commit.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Integrity error: %s", exc.orig)
        raise ConflictError("The request conflicts with existing data") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error")
        raise DatabaseUnavailableError("A database error occurred, please retry") from exc
