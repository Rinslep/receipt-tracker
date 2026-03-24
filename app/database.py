"""
database.py

Async SQLAlchemy engine and session factory setup. Creates the async engine
from DATABASE_URL (asyncpg), exposes an `AsyncSession` dependency for use in
FastAPI routes, and declares the shared `Base` for ORM model registration.
"""
