# src/shared/model_loader.py
"""
Centralized, side-effect-only imports so SQLAlchemy mappers are registered
without circular imports between model modules.
"""

def import_all_models() -> None:
    """
    Import model modules for their side-effects (mapper registration).
    Missing modules are ignored so startup remains robust during staged builds.
    """
    for path in (
        "src.identity.infrastructure.models",
        "src.platform.infrastructure.models",
        "src.messaging.infrastructure.models",
        "src.conversation.infrastructure.models",
        # add more domains as they land:
        # "src.healthcare.infrastructure.models",
        # "src.education.infrastructure.models",
        # "src.notifications.infrastructure.models",
    ):
        try:
            __import__(path)
        except ModuleNotFoundError:
            # Allow staged development: absent modules shouldn't kill startup
            continue
