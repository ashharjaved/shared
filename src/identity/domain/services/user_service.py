# # src/identity/domain/services/user_service.py
# from typing import List
# from ..entities.user import User
# from ..value_objects.role import Role
# from ..exception import AuthorizationError, ConflictError
# from ..repositories.user_repository import UserRepository
# from .password_service import PasswordService


# class UserService:
#     """Domain service for user management operations."""
    
#     def __init__(
#         self,
#         user_repository: UserRepository,
#         password_service: PasswordService
#     ):
#         self._user_repository = user_repository
#         self._password_service = password_service
    
#     def create_user(
#         self, 
#         requester: User, 
#         email: str,
#         display_name: str,
#         password: str,
#         tenant_id: str,
#         roles: List[Role]
#     ) -> User:
#         """
#         Create a new user with RBAC enforcement.
        
#         Args:
#             requester: User making the request
#             email: New user email
#             display_name: New user display name
#             password: Plain text password
#             tenant_id: Tenant ID for new user
#             roles: List of roles to assign
            
#         Returns:
#             Created User entity
            
#         Raises:
#             AuthorizationError: If requester lacks permission
#             ConflictError: If user already exists
#         """
#         # Enforce RBAC rules
#         if not self._can_create_user(requester, roles):
#             raise AuthorizationError("Insufficient permissions to create user with specified roles")
        
#         # Check if user already exists
#         existing_user = self._user_repository.find_by_email(email, tenant_id)
#         if existing_user:
#             raise ConflictError(f"User with email {email} already exists in tenant")
        
#         # Hash password
#         password_hash = self._password_service.hash_password(password)
        
#         # Create user entity
#         new_user = User.create(
#             email=email,
#             password_hash=password_hash,
#             tenant_id=tenant_id,
#             roles=roles
#         )
        
#         return new_user
    
#     def change_role(
#         self, 
#         requester: User, 
#         target_user_id: str, 
#         new_roles: List[Role]
#     ) -> User:
#         """
#         Change user roles with RBAC enforcement.
        
#         Args:
#             requester: User making the request
#             target_user_id: ID of user to modify
#             new_roles: New roles to assign
            
#         Returns:
#             Updated User entity
            
#         Raises:
#             AuthorizationError: If requester lacks permission
#         """
#         target_user = self._user_repository.find_by_id(target_user_id)
#         if not target_user:
#             raise ConflictError("User not found")
        
#         # Enforce RBAC rules
#         if not self._can_modify_user_roles(requester, target_user, new_roles):
#             raise AuthorizationError("Insufficient permissions to modify user roles")
        
#         old_roles = target_user.role.copy()
#         target_user.update_roles(new_roles)
                
#         return target_user
    
#     def deactivate_user(self, requester: User, target_user_id: str) -> User:
#         """
#         Deactivate a user account.
        
#         Args:
#             requester: User making the request
#             target_user_id: ID of user to deactivate
            
#         Returns:
#             Deactivated User entity
            
#         Raises:
#             AuthorizationError: If requester lacks permission
#         """
#         target_user = self._user_repository.find_by_id(target_user_id)
#         if not target_user:
#             raise ConflictError("User not found")
        
#         # Enforce RBAC rules
#         if not self._can_deactivate_user(requester, target_user):
#             raise AuthorizationError("Insufficient permissions to deactivate user")
        
#         target_user.deactivate()
        
#         # Raise domain event
#         event = UserDeactivated(
#             user_id=target_user.id,
#             tenant_id=target_user.tenant_id,
#             deactivated_by=requester.id
#         )
        
#         return target_user
    
#     def _can_create_user(self, requester: User, target_roles: List[Role]) -> bool:
#         """Check if requester can create user with specified roles."""
#         if Role.SUPER_ADMIN in requester.role:
#             return True
        
#         if Role.RESELLER_ADMIN in requester.role:
#             # Cannot create OwnerAdmin users
#             return Role.SUPER_ADMIN not in target_roles
        
#         if Role.TENANT_ADMIN in requester.role:
#             # Can only create Agent and ReadOnly users
#             allowed_roles = {Role.TENANT_USER, Role.READ_ONLY}
#             return all(role in allowed_roles for role in target_roles)
        
#         return False
    
#     def _can_modify_user_roles(
#         self, 
#         requester: User, 
#         target: User, 
#         new_roles: List[Role]
#     ) -> bool:
#         """Check if requester can modify target user's roles."""
#         # Cannot modify own roles
#         if requester.id == target.id:
#             return False
        
#         if Role.SUPER_ADMIN in requester.role:
#             return True
        
#         if Role.RESELLER_ADMIN in requester.role:
#             # Cannot modify OwnerAdmin or create OwnerAdmin
#             if Role.SUPER_ADMIN in target.role or Role.SUPER_ADMIN in new_roles:
#                 return False
#             return True
        
#         if Role.TENANT_ADMIN in requester.role:
#             # Can only modify Agent and ReadOnly users
#             allowed_roles = {Role.TENANT_USER, Role.READ_ONLY}
#             return (all(role in allowed_roles for role in target.role) and
#                    all(role in allowed_roles for role in new_roles))
        
#         return False
    
#     def _can_deactivate_user(self, requester: User, target: User) -> bool:
#         """Check if requester can deactivate target user."""
#         # Cannot deactivate self
#         if requester.id == target.id:
#             return False
        
#         if Role.SUPER_ADMIN in requester.role:
#             return True
        
#         if Role.RESELLER_ADMIN in requester.role:
#             # Cannot deactivate OwnerAdmin users
#             return Role.SUPER_ADMIN not in target.role
        
#         if Role.TENANT_ADMIN in requester.role:
#             # Can only deactivate Agent and ReadOnly users in same tenant
#             if target.tenant_id != requester.tenant_id:
#                 return False
#             allowed_roles = {Role.TENANT_USER, Role.READ_ONLY}
#             return all(role in allowed_roles for role in target.role)
        
#         return False