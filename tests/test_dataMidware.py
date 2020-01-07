import unittest
from dataGetter import dataMidware
from dataGetter import jianyanyuanGetter


class TestdataMidware_JianYanYuanData(unittest.TestCase):
    def setUp(self):
        self.j = dataMidware.JianYanYuanData()

    def tearDown(self):
        self.j.close()

    def test_JianYanYuanData_make_spot_record(self):
        datapoint = self.j._make_datapoint_param(self.j.device_list[2])
        __import__('pprint').pprint(self.j.make_spot_record(datapoint))

    def test_JianYanYuanData_make_spot(self):
        pass

    def test_JianYanYuanData_make_device(self):
        device_result = self.j.device_list[4]
        device = self.j.make_device(device_result)
        self.assertTrue(True)

    def test_JianYanYuanData_device(self):
        devices = self.j.device()
        # for n in devices:
        #     __import__('pprint').pprint(n)
        self.assertTrue(True)

    def test_JianYanYuanData_make_location(self):
        location = self.j.make_location(self.j.device_list[0])
        self.assertTrue(True)

    def test_JianYanYuanData_spot_record(self):
        pass


@unittest.skip('skip')
class TestdataMidware_XiaomiData(unittest.TestCase):
    pass
