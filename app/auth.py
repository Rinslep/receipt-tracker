from fastapi import Request, HTTPException
from jose import jwt, JWTError


async def get_current_user(request: Request) -> dict:
    """Extract authenticated user from Easy Auth headers, dev header, or JWT bearer token."""

    # Local dev convenience: X-Dev-User: <plain-user-id>
    dev_user = request.headers.get("X-Dev-User")
    if dev_user:
        return {"oid": dev_user, "name": dev_user, "email": dev_user}

    # App Service Easy Auth — injects these headers after validating the token
    principal_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    principal_name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if principal_id:
        return {
            "oid": principal_id,
            "name": principal_name or "User",
            "email": principal_name or "",
        }

    # Manual JWT validation (local dev with a real token)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return {
                "oid": payload.get("oid", ""),
                "name": payload.get("name", "User"),
                "email": payload.get("preferred_username", ""),
            }
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    raise HTTPException(status_code=401, detail="Not authenticated")
