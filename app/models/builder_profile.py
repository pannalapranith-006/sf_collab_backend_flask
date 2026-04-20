# Re-export BuilderProfile from the canonical builder module.
# This file exists so matchmaking services can import from app.models.builder_profile
# without defining a second SQLAlchemy mapper on the builder_profiles table.
from app.models.builder import BuilderProfile

__all__ = ["BuilderProfile"]
