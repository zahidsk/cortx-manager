#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          alerts.py
 Description:       Services for alerts handling

 Creation Date:     09/05/2019
 Author:            Alexander Nogikh
                    Prathamesh Rodi
                    Oleg Babin

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""
# Let it all reside in a separate controller until we've all agreed on request
# processing architecture
import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from csm.common.log import Log
from csm.common.services import Service, ApplicationService
from csm.common.queries import SortBy, SortOrder, QueryLimits, DateTimeRange
from csm.core.data.models.users import User, UserType, Passwd
from csm.common.errors import (CsmNotFoundError, CsmError, InvalidRequest,
                                CsmPermissionDenied, ResourceExist)
import time
from eos.utils.data.db.db_provider import (DataBaseProvider, GeneralConfig)
from eos.utils.data.access.filters import Compare, And, Or
from eos.utils.data.access import Query, SortOrder
from csm.core.blogic import const
from schematics import Model
from schematics.types import StringType, BooleanType, IntType
from typing import Optional, Iterable


class UserManager:
    """
    The class encapsulates user management activities.
    This is intended to be used during user management and authorization
    """
    def __init__(self, storage: DataBaseProvider) -> None:
        self.storage = storage

    async def create(self, user: User) -> User:
        """
        Stores a new user
        :param user: User model instance
        """
        # validate the model
        existing_user = await self.get(user.user_id)
        if existing_user:
            raise ResourceExist("Such user already exists", USERS_MSG_ALREADY_EXISTS,existing_user.user_id)

        return await self.storage(User).store(user)

    async def get(self, user_id) -> User:
        """
        Fetches a single user.
        :param user_id: User identifier
        :returns: User object in case of success. None otherwise.
        """
        Log.debug(f"Get user service user id:{user_id}")
        # TODO In absence of ComapareIgnoreCase manually filtering 
        # query = Query().filter_by(Compare(User.to_native("user_id").lower(), '=', user_id.lower()))
        # return next(iter(await self.storage(User).get(query)), None)
        all_users = await self.get_list()
        for user in all_users:
            if user["user_id"].lower() == user_id.lower():
                return user
        return None

    async def delete(self, user_id: str) -> None:
        Log.debug(f"Delete user service user id:{user_id}")
        await self.storage(User).delete(Compare(User.user_id, '=', user_id))

    async def get_list(self, offset: int = None, limit: int = None,
                       sort: SortBy = None) -> List[User]:
        """
        Fetches the list of users.
        :param offset: Number of items to skip.
        :param limit: Maximum number of items to return.
        :param sort: What field to sort on.
        :returns: A list of User models
        """
        query = Query()

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        if sort:
            query = query.order_by(getattr(User, sort.field), sort.order)
        Log.debug(f"Get user list service query: {query}")
        return await self.storage(User).get(query)

    async def count(self):
        return await self.storage(User).count(None)

    async def save(self, user: User):
        """
        Stores an already existing user.
        :param user:
        """
        # TODO: validate the model
        await self.storage(User).store(user)


USERS_MSG_USER_NOT_FOUND = "users_not_found"
USERS_MSG_PERMISSION_DENIED = "user_permission_denied"
USERS_MSG_ALREADY_EXISTS = "users_already_exists"
USERS_MSG_CANNOT_SORT = "users_non_sortable_field"
USERS_MSG_UPDATE_NOT_ALLOWED = "update_not_allowed"


class CsmUserService(ApplicationService):
    """
    Service that exposes csm user management actions from the csm core.
    """
    def __init__(self, user_mgr: UserManager):
        self.user_mgr = user_mgr

    def _user_to_dict(self, user: User):
        """ Helper method to convert user model into a dictionary repreentation """
        return {
            "id": user.user_id,
            "username": user.user_id,
            "user_type": user.user_type,
            "roles": user.roles,
            "created_time": user.created_time.isoformat() + 'Z',
            "updated_time": user.updated_time.isoformat() + 'Z'
        }

    async def create_user(self, user_id: str, password: str, **kwargs) -> dict:
        """
        Handles the csm user creation
        :param user_id: User identifier
        :param user_password: User password (not hashed)
        :param roles: List of roles of the user
        :param interfaces: List of user interfaces
        :returns: A dictionary describing the newly created user.
        In case of error, an exception is raised.
        """
        Log.debug(f"Create user service. user_id: {user_id}")
        user = User.instantiate_csm_user(user_id, password)
        user.update(kwargs)
        await self.user_mgr.create(user)
        return self._user_to_dict(user)

    async def create_root_user(self, user_id: str, password: str) -> dict:
        """
        Handles the preboarding root user creation
        :param user_id: User identifier
        :param password: User password (not hashed)
        :returns: A dictionary describing the newly created user.
        In case of error, an exception is raised.
        """
        Log.debug(f"Create root user service user_id: {user_id}")
        if await self.user_mgr.count() != 0:
            # The root user is allowed to be created only once during preboarding.
            # Non-zero user count means that such user was already created.
            return None

        # TODO: Decide the default preboarding user roles once we
        # implement user role management. Replace this hardcoded values
        # with proper constants.
        roles = ['root', 'manage']
        interfaces = ['web', 'cli', 'api']
        user = User.instantiate_csm_user(user_id, password, roles=roles,
                                         interfaces=interfaces)
        await self.user_mgr.create(user)
        return self._user_to_dict(user)

    async def get_user(self, user_id: str):
        """
        Fetches a single user.
        """
        Log.debug(f"Get user service user id: {user_id}")
        user = await self.user_mgr.get(user_id)
        if not user:
            raise CsmNotFoundError("There is no such user", USERS_MSG_USER_NOT_FOUND)
        return self._user_to_dict(user)

    async def get_user_list(self, limit, offset, sort_by, sort_dir):
        """
        Fetches the list of existing users.
        """
        user_list = await self.user_mgr.get_list(offset or None, limit or None,
            SortBy(sort_by, SortOrder.ASC if sort_dir == "asc" else SortOrder.DESC))

        field_mapping = {
            "id": "user_id",
            "username": "user_id"
        }
        if sort_by in field_mapping:
            sort_by = field_mapping[sort_by]

        if sort_by and sort_by not in const.CSM_USER_SORTABLE_FIELDS:
            raise InvalidRequest("It is impossible to sort by this field", USERS_MSG_CANNOT_SORT)

        return [self._user_to_dict(x) for x in user_list]

    async def delete_user(self, user_id: str):
        """ User deletion """
        Log.debug(f"Delete user service user_id: {user_id}.")
        user = await self.user_mgr.get(user_id)
        if not user:
            raise CsmNotFoundError("There is no such user", USERS_MSG_USER_NOT_FOUND)
        if self.is_super_user(user):
            raise CsmPermissionDenied("Can't delete super user",
                                      USERS_MSG_PERMISSION_DENIED, user_id)
        await self.user_mgr.delete(user.user_id)
        return {"message": "User Deleted Successfully."}

    async def _validation_for_update_by_superuser(self, user_id: str, user: User, new_values: dict):
        old_password = new_values.get("old_password", None)
        if self.is_super_user(user) and not old_password:
            raise InvalidRequest("Super user old password is required",
                                    USERS_MSG_UPDATE_NOT_ALLOWED, user_id)

        if self.is_super_user(user) and ('roles' in new_values):
            raise CsmPermissionDenied("Cannot change roles for super user",
                                    USERS_MSG_PERMISSION_DENIED, user_id)
    async def _validation_for_update_by_normal_user(self, user_id: str, loggedin_user_id: str,
                                                    new_values: dict):
        old_password = new_values.get("old_password", None)
        if user_id != loggedin_user_id:
            raise CsmPermissionDenied("Non super user cannot change other user",
                                    USERS_MSG_PERMISSION_DENIED, user_id)
        
        if not old_password:
            raise InvalidRequest("Old password is required",
                                    USERS_MSG_UPDATE_NOT_ALLOWED, user_id)

            if 'roles' in new_values:
                raise CsmPermissionDenied("Non super user cannot change roles for self",
                                        USERS_MSG_PERMISSION_DENIED, user_id)
       
    async def update_user(self, user_id: str, new_values: dict, loggedin_user_id: str) -> dict:
        Log.debug(f"Update user service user_id: {user_id}.")
        user = await self.user_mgr.get(user_id)
        if not user:
            raise CsmNotFoundError("There is no such user", USERS_MSG_USER_NOT_FOUND)

        old_password = new_values.get("old_password", None)
        loggedin_user = await self.user_mgr.get(loggedin_user_id)
        # Is Logged in user super user
        if self.is_super_user(loggedin_user):
            await self._validation_for_update_by_superuser(user_id, user, new_values)
        else:
            await self._validation_for_update_by_normal_user(user_id, loggedin_user_id, new_values)
        
        if old_password and not self._verfiy_old_password(user, old_password):
            raise InvalidRequest("Cannot change password without valid old password",
                                      USERS_MSG_UPDATE_NOT_ALLOWED)
        
        user.update(new_values)
        await self.user_mgr.save(user)
        return self._user_to_dict(user)

    def _verfiy_old_password(self, user: User, password):
        return Passwd.verify(password, user.password_hash)

    def is_super_user(self, user: User):
        """ Check if user is super user """
        return const.CSM_SUPER_USER_ROLE in user.roles
