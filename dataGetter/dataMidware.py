from threading import Timer
from typing import (
    NewType, Dict, Optional, Tuple, List, Generator, NamedTuple,
    TypedDict, Iterator, Callable, cast)
from abc import ABC, abstractmethod
from collections import namedtuple
from sys import maxsize
from datetime import datetime as dt
from operator import itemgetter
import logging
from functools import partial

import xiaomiGetter as xGetter
import jianyanyuanGetter as jGetter
from jianyanyuanGetter import (
    DataPointParam as JdpParam,
    DataPointResult as JdpResult,
    DeviceParam as JdevParam,
    DeviceResult as JdevResult)
import authConfig
from utils import str_to_datetime, datetime_to_str
from dateSequence import DateSequence, date_sequence


class Location(NamedTuple):
    climate_area: str
    province: str
    city: str


class Spot(NamedTuple):
    project_id: int
    spot_id: int
    spot_name: str
    spot_type: str


class SpotRecord(NamedTuple):
    # spot_id: int
    spot_record_time: dt
    temperature: Optional[float]
    humidity: Optional[float]
    pm25: Optional[float]
    co2: Optional[float]
    window_opened: Optional[bool]
    ac_power: Optional[float]


class Device(NamedTuple):
    spot_id: int
    device_name: str


class SpotData(ABC):
    """
    A Factory
    Common interface for spot data from different sources.
    """
    token_fetch_error_msg: str = 'Token fetch Error: Token Error'
    datetime_time_eror_msg: str = 'Datetime error: Incorrect datetime'

    @abstractmethod
    def spot_location(self) -> Optional[Generator[Optional[Spot], None, None]]:
        """
        Get spot location information.
        It returns a generator of the list of spot location information
        value returned are used to fill `spot` table in database schema.
        """

    @abstractmethod
    def spot_record(self, spot_id: Optional[int] = None
                    ) -> Optional[Generator[Optional[SpotRecord], None, None]]:
        """
        Get spot record data include temperature, humidity pm2.5 etc.
        value returned are used to fill `spot_record` table in database schema.
        """

    @abstractmethod
    def device(self) -> Optional[Generator[Optional[Device], None, None]]:
        """
        Get device information
        value returned will be used to fill `device` table in database schema.
        """


class RealTimeSpotData(ABC):
    """ RealTime mixin """
    token_fetch_error_msg: str = 'Token fetch Error: Xiaomi Token Error, didn\'t refresh token'
    datetime_time_eror_msg: str = 'Datetime error: Incorrect datetime'

    @abstractmethod
    def rt_spot_record(self) -> Optional[Generator[Optional[SpotRecord], dt, str]]:
        """
        Get spot record data include temperature, humidity pm2.5 etc in real time.
        value returned are used to fill `spot_record` table in database schema.
        """


class XiaoMiData(SpotData, RealTimeSpotData):
    """
    Xiaomi data getter implementation
    """
    source: str = '<xiaomi>'

    def __init__(self):
        # get authcode and token
        self.auth: xGetter.AuthData = authConfig.xauth
        self.token: Optional[xGetter.TokenResult] = xGetter._get_token(self.auth)
        self.refresh: Optional[str] = None
        if not self.token:
            logging.critical('%s %s', self.source, Spot.token_fetch_error_msg)
            raise ConnectionError(self.source, Spot.token_fetch_error_msg)

        def _refresh_token():  # token will expire. So need to be refreshed periodcially.
            self.refresh = self.token['refresh_token']
            self.token = xGetter._get_token(self.auth, self.refresh)
            if not self.token:
                logging.critical('%s %s', self.source, Spot.token_fetch_error_msg)
                raise ConnectionError(self.source, Spot.token_fetch_error_msg)

            # reset timer.
            self.timer = Timer(self.token['expires_in'] - 200, _refresh_token)
            self.timer.start()
        self.timer = Timer(self.token['expires_in'] - 200, _refresh_token)  # spin timer.
        self.timer.start()

    def spot_location(self) -> Optional[Generator]:
        pass

    def spot_record(self, spot_id: Optional[int] = None) -> Optional[Generator]:
        pass

    def device(self) -> Optional[Generator]:
        pass

    def rt_spot_record(self) -> Optional[Generator]:
        pass


class JianYanYuanData(SpotData, RealTimeSpotData):
    """
    Jianyanyuan data getter implementation
    """
    source: str = '<jianyanyuan>'
    expire_in: int = 20  # token is valid in 20 seconds.
    indoor_data_collector_pid: str = '001'
    monitor_pid: str = '003'

    size: int = 300
    device_params: JdevParam = {  # prepare device parameter.
        'companyId': 'HKZ',
        'start': 1,
        'size': size,
        'pageNo': 1,
        'pageSize': str(size)
    }

    def __init__(self, datetime_range: Optional[Tuple[dt, dt]] = None):
        self.auth = authConfig.jauth
        self.token = jGetter._get_token(self.auth)

        if datetime_range is not None:  # data within this date will be collected.

            self.startAt, self.endWith = datetime_range

        if not self.token:

            logging.critical('%s %s', self.source, SpotData.token_fetch_error_msg)
            raise ConnectionError(self.source, SpotData.token_fetch_error_msg)

        def _refresh_token():
            self.token = jGetter._get_token(self.auth)

            if not self.token:
                logging.critical('%s %s', self.source, Spot.token_fetch_error_msg)
                raise ConnectionError(self.source, Spot.token_fetch_error_msg)

            self.timer = Timer(JianYanYuanData.expire_in - 5, _refresh_token)
            self.timer.start()

        self.timer = Timer(JianYanYuanData.expire_in - 5, _refresh_token)
        self.timer.start()

        # common states
        self.device_list = jGetter._get_device_list(
            self.auth, self.token, cast(Dict, JianYanYuanData.device_params))

    def spot_location(self) -> Optional[Generator]:
        """
        return location in standard format
        """

        # define utils.
        location_attrs: Tuple[str, ...] = (
            'cityIdLogin', 'provinceIdLogin', 'nickname', 'address',
            'provinceLoginName', 'cityLoginName', 'location')

        if self.device_list is None:
            logging.error('empty device list')
            return None

        # filter location attributes from device result lists.
        make_attrs: Callable = partial(
            JianYanYuanData._filter_location_attrs,
            location_attrs=location_attrs)

        attrses: Iterator = map(make_attrs, self.device_list)

        make_spot = JianYanYuanData.make_spot
        return (make_spot(attrs) for attrs in attrses)

    def spot_record(self) -> Optional[Generator]:
        """
        Return  Generator of SpotRecord of a specific Spot
        """
        pass

    def device(self) -> Optional[Generator]:
        pass

    ####################################
    #  spot_location helper functions  #
    ####################################

    @staticmethod
    def _filter_location_attrs(device_result: JdevResult,
                               location_attrs: Tuple[str, ...]) -> Dict:
        """
        filter location attributes from device results
        """
        return {k: v for k, v
                in device_result.items()
                if k in location_attrs}

    @staticmethod
    def make_spot(attrs: Dict) -> Optional[Spot]:
        """
        construct `Spot` type from given location attrs.

        Priority of attrs:

            address > nickname > cityLoginName > provinceLoginName > cityId or provinceId

        if address and nickname both exsits, commbine them together as the spot name.
        """
        # TODO: pick the most suitable infor from locatino attrs 2019-12-23 @1
        # Location need to match with project.
        # So this function need to be implemented with project information.

        return attrs

    ##################################
    #  spot_record helper functions  #
    ##################################

    def datapoint_param_iter(self) -> Optional[Iterator]:
        """
        datapoint paramter generator. Each paramter for each device.
        """
        if self.device_list is None:
            return None

        datapoint_param_iter: Iterator = (
            JianYanYuanData._make_datapoint_param(p)
            for p
            in self.device_list)

        if not any(datapoint_param_iter):

            logging.warning(JianYanYuanData.source + 'No datapoint parameter.')
            return None

        return datapoint_param_iter

    def datapoint_iter(self,
                       datapoint_param_iter: Optional[Iterator]
                       ) -> Optional[Iterator
                                     [Optional
                                      [List[JdpResult]]]]:
        """ datapoint data generator. Is a iterator of list.  """

        if datapoint_param_iter is None:
            logging.error('empty datapoint_param_iter')
            return None

        datapoint_iter = (
            jGetter._get_data_points(self.auth, self.token, param)
            for param
            in datapoint_param_iter)

        if not any(datapoint_iter):
            logging.warning(JianYanYuanData.source + 'No datapoint list.')
            return None

        return datapoint_iter

    @staticmethod
    def make_spot_record(datapoint: Optional[JdpResult]) -> Optional[SpotRecord]:
        """ construct `SpotRecord` from given datapoint_params """

        if datapoint is None:
            logging.error('datapoint is empty')
            return None

        aS: Optional[Dict] = datapoint.get('as')

        if aS is None:
            logging.error('datapoint `as` record is empty')
            return None

        key: Optional[str] = datapoint.get('key')
        if key is None:
            logging.error('datapoint `key` record is empty')
            return None

        time = str_to_datetime(key)

        pm25: Optional[float] = aS.get(jGetter.attrs['pm25'])
        co2: Optional[float] = aS.get(jGetter.attrs['co2'])
        temperature: Optional[float] = aS.get(jGetter.attrs['temperature'])
        humidity: Optional[float] = aS.get(jGetter.attrs['humidity'])
        ac_power: Optional[float] = aS.get(jGetter.attrs['ac_power'])

        return SpotRecord(time, temperature, humidity, pm25, co2, None, ac_power)

    @staticmethod
    def _make_datapoint_param(device_result: JdevResult,
                              time_range: Optional[Tuple[str, str]] = None
                              ) -> Optional[JdpParam]:
        """
        make query parameter datapoint query.
        DataPoint query parameter format:
            gid: str
            did: str
            aid: int
            startTime: str, yyyy-MM-ddTHH:mm:ss
            endTime: str, yyyy-MM-ddTHH:mm:ss

        modelName, prodcutId for devices: 'ESIC-SN\\d{2,2}',     '001', indoor data
                                          'ESIC-DTU-RB-RF06-2G', '003', AC power
        """
        if not device_result:
            logging.error('no device result')
            return None

        (gid, did, productId, createTime) = itemgetter(
            'gid', 'deviceId', 'productId', 'createTime')(device_result)

        # Note: Don't need get attrs since we already know what to get,
        # attrs: Optional[List[jGetter.AttrResult]] = (
        #     jGetter._get_device_attrs(self.auth, self.token, gid))

        if not time_range:
            startTime: str = createTime
            endTime: str = datetime_to_str(dt.utcnow())
        # check if datetimes are valid

        else:
            startTime, endTime = time_range

            if str_to_datetime(startTime) < str_to_datetime(createTime):
                raise ValueError(JianYanYuanData.source,
                                 SpotData.datetime_time_eror_msg,
                                 startTime,
                                 createTime)

            if str_to_datetime(endTime) > dt.utcnow():
                raise ValueError(JianYanYuanData.source,
                                 SpotData.datetime_time_eror_msg,
                                 endTime)

        aid: str = JianYanYuanData._get_aid(productId)

        datapoint_params: Optional[JdpParam] = (
            jGetter.DataPointParam(
                gid=gid,
                did=did,
                aid=aid,
                startTime=startTime,
                endTime=endTime))
        return datapoint_params

    # set attr id
    # Here ignored all haier devices.
    @staticmethod
    def _get_aid(productId) -> str:

        if productId == JianYanYuanData.indoor_data_collector_pid:
            return '{},{},{},{}'.format(
                jGetter.attrs['pm25'],
                jGetter.attrs['co2'],
                jGetter.attrs['temperature'],
                jGetter.attrs['humidity'])

        if productId == JianYanYuanData.monitor_pid:
            return jGetter.attrs['ac_power']
        return ''

    ######################
    #  Implement device  #
    ######################

    def rt_spot_record(self):
        pass


# TODO Outdoor data
class OutdoorData:
    pass

