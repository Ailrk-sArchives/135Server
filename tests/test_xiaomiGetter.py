from typing import Optional
import unittest
from dataGetter import xiaomiGetter as x
from dataGetter import authConfig
from dataGetter import dataMidware
import time
xauth = authConfig.xauth


class XiaomiGetterTest(unittest.TestCase):
    def setUp(self):
        self.token = x._get_token(xauth)

    def test_get_auth_code(self):
        authcode: Optional[str] = x._get_auth_code(xauth)
        self.assertTrue(authcode is not None)

    def test_get_token(self):
        token: Optional[x.TokenResult] = x._get_token(xauth)
        self.assertTrue(token is not None and 'access_token' in token)

    def test_get_token_refresh(self):
        oldtoken = dict(**self.token)
        self.token = x._get_token(xauth, refresh=self.token)

        self.assertTrue(oldtoken['access_token'] != self.token['access_token'])

    def test_gen_sign(self):
        sign: Optional[str] = x._gen_sign(xauth, self.token)
        self.assertTrue(sign is not None)

    def test_get_pos(self):
        params: x.PosParam = {'positionId': 'real2.557305651542360064'}
        pos: Optional[x.PosResult] = x._get_pos(xauth, self.token, params)
        __import__('pprint').pprint(pos)
        self.assertTrue(pos is not None)

    def test_get_device(self):
        dev: Optional[x.DeviceResult] = x._get_device(xauth, self.token)
        self.assertTrue(dev is not None)

    def test_get_resource(self):
        params: x.ResourceParam = {
            'data': [{'did': 'lumi.158d0002374da1', 'attrs': ['3', 'humidity_value']}]}
        res: Optional[x.ResourceResult] = x._get_resource(xauth, self.token, params)
        self.assertTrue(res is not None)


