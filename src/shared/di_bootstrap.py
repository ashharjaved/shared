# from __future__ import annotations
# from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# from src.shared.di import services
# #from src.conversation.application.factories import provide_flow_service, SessionFactory as FlowSF  # your existing flow factories.py
# #from src.appointmant.application.policy_factories import provide_policy_service, SessionFactory as PolicySF

# FLOW_SERVICE_KEY = "conversation.flow_service"
# POLICY_SERVICE_KEY = "appointmant.policy_service"

# def register_services(session_factory: async_sessionmaker[AsyncSession]) -> None:
#     # Register factories once (idempotent at app boot). If reloaded, let it fail loudly to catch duplicates.
#     #services.register(FLOW_SERVICE_KEY, lambda: provide_flow_service(session_factory))
#     #services.register(POLICY_SERVICE_KEY, lambda: provide_policy_service(session_factory))
