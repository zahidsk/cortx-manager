# CORTX-CSM: CORTX Management web and CLI interface.
# Copyright (c) 2022 Seagate Technology LLC and/or its Affiliates
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.

from typing import Any
import json
from csm.core.services.rgw.s3.utils import CsmRgwConfigurationFactory
from csm.core.data.models.rgw import RgwErrors, RgwError
from csm.common.errors import CsmInternalError
from csm.common.payload import Json, Payload, JsonMessage, Dict
from csm.common.utility import Utility
from cortx.utils.log import Log
from csm.core.blogic import const
from cortx.utils.s3 import S3Client
from cortx.utils.s3 import S3ClientException


class RGWPlugin:

    def __init__(self):
        """
        Initialize RGW plugin
        """
        config = CsmRgwConfigurationFactory.get_rgw_connection_config()
        self._rgw_admin_client = S3Client(config.auth_user_access_key,
            config.auth_user_secret_key, url=config.url, timeout=const.S3_CONNECTION_TIMEOUT)
        self._api_operations = Json(const.RGW_ADMIN_OPERATIONS_MAPPING_SCHEMA).load()
        self._api_response_mapping_schema = Json(const.IAM_OPERATIONS_MAPPING_SCHEMA).load()
        self._api_suppress_payload_schema = Json(const.SUPPRESS_PAYLOAD_SCHEMA).load()

    @Log.trace_method(Log.DEBUG, exclude_args=['access_key', 'secret_key'])
    async def execute(self, operation, **kwargs) -> Any:
        api_operation = self._api_operations.get(operation)
        request_body = self._build_request(api_operation['REQUEST_BODY_SCHEMA'], **kwargs)
        return await self._process(api_operation, request_body, operation)

    @Log.trace_method(Log.DEBUG, exclude_args=['access_key', 'secret_key'])
    def _build_request(self, request_body_schema, **kwargs) -> Any:
        request_body = dict()
        for key, value in request_body_schema.items():
            if kwargs.get(key, None) is not None:
                request_body[value] = kwargs.get(key, None)
        return request_body

    @Log.trace_method(Log.DEBUG, exclude_args=['access_key', 'secret_key'])
    async def _process(self, api_operation, request_body, operation) -> Any:
        try:
            (code, body) = await self._rgw_admin_client.signed_http_request(api_operation['METHOD'], api_operation['ENDPOINT'], query_params=request_body)
            response_body = json.loads(body) if body else {}
            if code != api_operation['SUCCESS_CODE']:
                return self._create_error(code, response_body)
            suppressed_response = self._supress_response_keys(operation, response_body)
            return self._build_response(operation, suppressed_response)
        except S3ClientException as rgwe:
            Log.error(f'{const.S3_CLIENT_ERROR_MSG}: {rgwe}')
            if str(rgwe) == "Request timeout":
                return self._create_error(408, const.S3_CLIENT_ERROR_CODES[408])
            if "Cannot connect to" in str(rgwe):
                return self._create_error(503, const.S3_CLIENT_ERROR_CODES[503])
            raise CsmInternalError(const.S3_CLIENT_ERROR_MSG)
        except Exception as e:
            Log.error(f'{const.UNKNOWN_ERROR}: {e}')
            raise CsmInternalError(const.S3_CLIENT_ERROR_MSG)

    @Log.trace_method(Log.DEBUG, exclude_args=['access_key', 'secret_key'])
    def _build_response(self, operation, response) -> Any:
        """
        This method maps the raw response to the required schema
        based on the given operation.

        Args:
            operation (str): IAM operation.
            response (dict): Response from s3 server.

        Returns:
            Mapped response.
        """
        mapped_response = response
        mapping = self._api_response_mapping_schema.get(operation)
        if mapping:
            try:
                Log.info(f'Performing raw response mapping for {operation}')
                raw_response_payload = Payload(JsonMessage(json.dumps(response)))
                parsed_response_payload = Payload(Dict(dict()))
                raw_response_payload.convert(mapping, parsed_response_payload)
                parsed_response_payload.dump()
                mapped_response = parsed_response_payload.load()
                RGWPlugin._params_cleanup(mapped_response)
            except Exception as e:
                Log.error(f"Error occured while coverting raw api response to\
                    required response: {e}")
                raise e
        return mapped_response

    def _supress_response_keys(self, operation, response) -> Any:
        """
        Remove specific keys from response based on an operation.

        Args:
            operation (str): IAM operation.
            response (dict): Response from s3 server.

        Returns:
            Modified response.
        """
        suppressed_response = response
        keys = self._api_suppress_payload_schema.get(operation)
        if keys:
            Log.info("Suppressing keys from raw response.")
            try:
                for key in keys:
                    suppressed_response = Utility.remove_json_key(suppressed_response, key)
            except Exception as e:
                Log.error(f"Error occured while suppressing {keys} keys from response: {e}")
                raise e
        return suppressed_response

    @staticmethod
    def _params_cleanup(params):
        """
        Removes the first level keys from dict whos values are None.
        Args:
            params (dict): Mapped response as per operation's schema.
        """
        for key, value in list(params.items()):
            if value is None:
                params.pop(key)

    def _create_error(self, status: int, body: dict) -> Any:
        """
        Converts a body of a failed query into RgwError object.

        :param status: HTTP Status code.
        :param body: parsed HTTP response (dict) with the error's decription.
        :returns: instance of error.
        """

        Log.error(f"Create error body: {body}")

        rgw_error = RgwError()
        rgw_error.http_status = status
        rgw_error.error_code = RgwErrors[body['Code']]
        rgw_error.error_message = rgw_error.error_code.value

        return rgw_error
