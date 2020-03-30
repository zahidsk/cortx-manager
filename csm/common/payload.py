#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          payload.py
 Description:       Provide payload for various file.

 Creation Date:     31/05/2018
 Author:            Ujjwal Lanjewar
                    Ajay Paratmandali

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""

import os, errno, sys
import json, toml, yaml, tarfile
import configparser
from typing import List


class Doc:
    _type = dict

    def __init__(self, source):
        self._source = source

    def __str__(self):
        return str(self._source)

    def load(self):
        ''' Loads data from file of given format '''
        if not os.path.exists(self._source):
            return {}
        try:
            return self._load()
        except Exception as e:
            raise Exception('Unable to read file %s. %s' % (self._source, e))

    def dump(self, data):
        ''' Dump the anifest file to desired file or to the source '''
        dir_path = os.path.dirname(self._source)
        if len(dir_path) > 0 and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        self._dump(data)

class Toml(Doc):
    ''' Represents a TOML doc '''

    def __init__(self, file_path):
        Doc.__init__(self, file_path)

    def _load(self):
        with open(self._source, 'r') as f:
            return toml.load(f, dict)

    def _dump(self, data):
        with open(self._source, 'w') as f:
            toml.dump(data, f)

class Json(Doc):
    ''' Represents a JSON doc '''

    def __init__(self, file_path):
        Doc.__init__(self, file_path)

    def _load(self):
        with open(self._source, 'r') as f:
            return json.load(f)

    def _dump(self, data):
        with open(self._source, 'w') as f:
            json.dump(data, f, indent=2)

class Yaml(Doc):
    ''' Represents a YAML doc '''

    def __init__(self, file_path):
        Doc.__init__(self, file_path)

    def _load(self):
        with open(self._source, 'r') as f:
            return yaml.safe_load(f)

    def _dump(self, data):
        with open(self._source, 'w') as f:
            yaml.dump(data, f)

class Tar(Doc):
    """Represents Tar File"""

    def __init__(self, file_path):
        Doc.__init__(self, file_path)

    def _dump(self, files: List):
        """
        will create a tar file at source path.
        :param files: Files and Directories to be Included in Tar File.
        :return: None
        """
        with tarfile.open(self._source, "w:gz") as tar:
            for each_file in files:
                tar.add(each_file, arcname=os.path.basename(each_file),
                    recursive=True)

class Ini(Doc):
    ''' Represents a YAML doc '''

    def __init__(self, file_path):
        self._config = configparser.ConfigParser()
        Doc.__init__(self, file_path)
        self._type = configparser.SectionProxy

    def _load(self):
        self._config.read(self._source)
        return self._config

    def _dump(self, data):
        with open(self._source, 'w') as f:
            data.write(f)

class Dict(Doc):
    '''Represents Dictionary Without file'''

    def __init__(self, data={}):
        Doc.__init__(self, data)

    def load(self):
        return self._source

    def dump(self, data):
        self._source = data

class JsonMessage(Json):
    def __init__(self, json_str):
        """
        Represents the Json Without FIle
        :param json_str: Json String to be processed :type: str
        """
        Json.__init__(self, json_str)

    def load(self):
        """
        Load the json to python interpretable Dictionary Object
        :return: :type: Dict
        """
        return json.loads(self._source)

    def dump(self, data: dict):
        """
        Set's the data _source after converting to json
        :param data: :type: Dict
        :return:
        """
        self._source = json.dumps(data)

class Payload:
    ''' implements a Payload in specified format. '''

    def __init__(self, doc):
        self._dirty = False
        self._doc = doc
        self.load()

    def load(self):
        if self._dirty:
            raise Exception('%s not synced to disk' % self._doc)
        self._data = self._doc.load()
        return self._data

    def dump(self):
        ''' Dump the anifest file to desired file or to the source '''
        self._doc.dump(self._data)
        self._dirty = False

    def _get(self, key, data):
        ''' Obtain value for the given key '''
        k = key.split('.', 1)
        if k[0] not in data.keys(): return None
        return self._get(k[1], data[k[0]]) if len(k) > 1 else data[k[0]]

    def get(self, key):
        if self._data is None:
            raise Exception('Configuration %s not initialized' % self._doc)
        return self._get(key, self._data)

    def _set(self, key, val, data):
        k = key.split('.', 1)
        if len(k) == 1:
            data[k[0]] = val
            return
        if k[0] not in data.keys() or type(data[k[0]]) != self._doc._type:
            data[k[0]] = {}
        self._set(k[1], val, data[k[0]])

    def set(self, key, val):
        ''' Sets the value into the DB for the given key '''
        self._set(key, val, self._data)
        self._dirty = True

    def convert(self, map, payload):
        """
        Converts 1 Schema to 2nd Schema depending on mapping dictionary.
        :param map: mapping dictionary :type:Dict
        :param payload: Payload Class Object with desired Source.
        :return: :type: Dict
        Mapping file example - 
        key <input schema> : value <output schema>
        """
        for key in map.keys():
            val = self.get(key)
            payload.set(map[key], val)
        return payload

    def data(self):
        return self._data
