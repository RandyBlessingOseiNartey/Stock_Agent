import uuid

from fastapi import Header

# TODO: replace with real authentication (JWT / session cookie / OAuth)
# before any production launch. This stub exists only so every downstream
# feature (especially Chat, which requires a user_id for its database
# schema) has something to key off of during development.
_DEV_FALLBACK_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user_id(x_user_id: str | None = Header(default=None)) -> uuid.UUID:
    """
    Reads a client-supplied X-User-Id header if present and valid;
    otherwise falls back to one fixed placeholder UUID for local
    development. This is NOT authentication — anyone can claim any
    user_id by setting the header. Replace before production.
    """
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            pass
    return _DEV_FALLBACK_USER_ID
