#!/usr/share/env python3

from csm.core.blogic import const
from csm.cli.command_factory import CommandFactory
from argparse import ArgumentError
import unittest
import json
import os
from csm.test.common import Const

permissions = {
            'users': { 'list': True, 'update': True, 'delete': True }
}

delete_command = CommandFactory.get_command(
    ["users", 'delete', "user123"], permissions)
t = unittest.TestCase()
file_path = Const.MOCK_PATH

with open(file_path + "csm_user_commands_output.json") as fp:
    EXPECTED_OUTPUT = json.loads(fp.read())


def test_1(*args):
    expected_output = 'users'
    actual_output = delete_command.name
    t.assertEqual(actual_output, expected_output)


def test_2(*args):
    expected_output = EXPECTED_OUTPUT.get("expected_csm_user_delete")
    actual_output = delete_command.options
    t.assertDictEqual(actual_output, expected_output)


def test_3(*args):
    expected_output = 'delete'
    actual_output = delete_command.method
    t.assertEqual(actual_output, expected_output)


def init(args):
    pass


test_list = [test_1, test_2, test_3]
