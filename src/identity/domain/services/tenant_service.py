# from __future__ import annotations
# from typing import Optional
# from uuid import UUID

# from src.identity.domain.entities.tenant import Tenant, TenantType, SubscriptionPlan
# from src.identity.domain.value_objects.role import Role
# from src.shared.exceptions import AuthorizationError
# from src.shared.error_codes import ERROR_CODES


# class TenantDomainService:
#     """
#     Domain-level rules for tenant lifecycle.
#     Pure business logic: RBAC checks, hierarchy validation, and factory creation.
#     Does not touch repositories or external services.
#     """

#     @staticmethod
#     def authorize_create_tenant(
#         *,
#         requester_role: Role,
#         requester_tenant: Optional[UUID],
#         new_tenant_type: TenantType,
#         parent_id: Optional[UUID],
#     ) -> None:
#         """
#         Enforce RBAC rules for tenant creation:
#           - SUPER_ADMIN can create RESELLER or TENANT (anywhere).
#           - RESELLER_ADMIN can only create TENANT under its own tenant.
#         """
#         if requester_role == Role.SUPER_ADMIN:
#             return
#         elif requester_role == Role.RESELLER_ADMIN:
#             if new_tenant_type != TenantType.TENANT or parent_id != requester_tenant:
#                 raise AuthorizationError(
#                     ERROR_CODES["forbidden"]["message"],
#                     code="forbidden",
#                     status_code=403,
#                 )
#         else:
#             raise AuthorizationError(
#                 ERROR_CODES["forbidden"]["message"],
#                 code="forbidden",
#                 status_code=403,
#             )

#     @staticmethod
#     def create_tenant_entity(
#         *,
#         name: str,
#         tenant_type: TenantType,
#         parent_id: Optional[UUID],
#         plan: SubscriptionPlan,
#     ) -> Tenant:
#         """
#         Factory method for new Tenant entity.
#         Assigns defaults and enforces invariants.
#         """
#         return Tenant.new(
#             name=name,
#             tenant_type=tenant_type,
#             parent_id=parent_id,
#             subscription_plan=plan,
#         )