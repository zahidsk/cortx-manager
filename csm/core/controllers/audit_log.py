#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          audit_log.py
 Description:       Implementation of audit logs views

 Creation Date:     02/06/2019
 Author:            Mazhar Inamdar

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""
import json
from csm.core.services.file_transfer import FileType
from csm.common.log import Log
from csm.core.controllers.view import CsmView, CsmResponse, CsmAuth


@CsmView._app_routes.view("/api/v1/auditlogs/show/{component}")
class AuditLogShowView(CsmView):
    def __init__(self, request):
        super(AuditLogShowView, self).__init__(request)
        self._service = self.request.app["audit_log"]
        self._service_dispatch = {}

    """
    GET REST implementation for fetching audit logs
    """
    async def get(self):
        Log.debug("Handling audit log fetch request")
        request_data = self.request.rel_url.query
        component = self.request.match_info["component"]
        start_date = self.request.rel_url.query["start_date"]
        end_date = self.request.rel_url.query["end_date"] 
        return await self._service.get_by_range(component, start_date, end_date)

@CsmView._app_routes.view("/api/v1/auditlogs/download/{component}")
class AuditLogDownloadView(CsmView):
    def __init__(self, request):
        super(AuditLogDownloadView, self).__init__(request)
        self._service = self.request.app["audit_log"]
        self._file_service = self.request.app["download_service"]
        self._service_dispatch = {}

    """
    GET REST implementation for fetching audit logs
    """
    async def get(self):
        Log.debug("Handling audit log fetch request")
        request_data = self.request.rel_url.query
        component = self.request.match_info["component"]
        start_date = self.request.rel_url.query["start_date"]
        end_date = self.request.rel_url.query["end_date"]
        zip_file = await self._service.get_audit_log_zip(component, start_date, end_date)
        return self._file_service.get_file_response(FileType.AUDIT_LOG, zip_file)
