"""
auth.py

Authentication and authorisation helpers. Handles Azure AD / Entra ID token
validation via MSAL, extracts user claims from JWT bearer tokens, and provides
FastAPI dependency-injection utilities for protecting routes.
"""
