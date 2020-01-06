import requests
from hashlib import md5, sha1
from typing import NewType, Dict, Optional, Tuple, TypedDict, List, Callable, cast, TypeVar
from operator import itemgetter
import urllib.parse
from datetime import datetime as dt
from utils import currentTimestamp
import json
import logging

AuthData = (
    TypedDict('AuthData',
              {'account': str,
               'password': str,
               'appId': str,            # called client_id in json request.
               'appKey': str,           # called client_secret in json request.

               'state': str,            # arbitrary string.
               'redirect_uri': str,     # callback uri, see document.

               'auth_base_url': str,
               'authorize_url': str,
               'token_url': str,

               'grant_type': str,
               'refresh_token': str,    # only needed when need to refresh token.

               'api_query_base_url': str,
               'api_query_pos_url': str,
               'api_query_dev_url': str,
               'api_query_resrouce_url': str}, total=False))


PosParam = (  # Method: Get
    TypedDict('PosParam',
              {'positionId': str,
               'pageNum': int,
               'pageSize': int}, total=False))

DeviceParam = (
    TypedDict('DeviceParam',
              {'did': str,
               'positionId': str,
               'pageNum': int,
               'pageSize': int}, total=False))

# Nested type declaration
OneResourceParam = (
    TypedDict('OneResourceParam',
              {'did': str,
               'attrs': List[str]}))


class ResourceParam(TypedDict):
    data: List[OneResourceParam]


TokenResult = TypedDict('TokenResult',
                        {'access_token': str,
                         'refresh_token': str,
                         'openId': str,
                         'state': str,
                         'token_type': str,
                         'expires_in': int})

PosData = TypedDict('PosData',
                    {'positionName': str,
                     'positionId': str,
                     'description': str,
                     'createTime': str})


class PosResult(TypedDict):
    data: List[PosData]
    totalCount: int


DeviceData = TypedDict('DeviceData',
                       {'did': str,
                        'name': str,
                        'model': str,
                        'parentId': str,
                        'positionId': str,
                        'state': int,
                        'registerTime': str})


class DeviceResult(TypedDict):
    data: List[DeviceData]
    totalCount: int


ResourceData = TypedDict('ResourceData', {'did': str, 'attr': str, 'value': str, 'time': int})
ResourceResult = List[ResourceData]

###############################################


def _get_auth_code(auth: AuthData) -> Optional[str]:

    """ return auth code """

    (client_id,
     auth_base_url,
     authorize_url,
     redirect_uri,
     state,
     account,
     password) = itemgetter('appId', 'auth_base_url', 'authorize_url', 'redirect_uri', 'state',
                            'account', 'password')(auth)

    # First get to the login page
    url: str = urllib.parse.urljoin(auth_base_url, authorize_url)
    getparam: Dict = {'client_id': client_id,
                      'response_type': 'code',
                      'redirect_uri': redirect_uri,
                      'state': state}
    login_url: str = url + '?' + urllib.parse.urlencode(getparam)

    # Second step is to login with account and password to get auth code.
    postparam: Dict = dict({'account': account, 'password': password})

    response: requests.Response = requests.post(login_url, data=postparam)
    response_url: str = response.url

    # get auth code from parameters in returned url.
    if 'code' not in response_url:
        logging.error('authenticion error')
        return None

    returned_params: str = urllib.parse.urlsplit(response_url).query
    query: Dict = {k: v[0] for k, v in urllib.parse.parse_qs(returned_params).items()}
    return query['code']


def _get_token(auth: AuthData, refresh: Optional[TokenResult] = None) -> Optional[TokenResult]:

    """
    return token with given auth code
    if refresh token is passed, it is then used to retreive new token.
    """
    # TODO refresh
    def _auth_refresh_token(params: Dict, token: TokenResult) -> Dict:
        """ return auth data for refreshing token """
        newparams = dict(**params)
        newparams['refresh_token'] = token['refresh_token']
        newparams['grant_type'] = 'refresh_token'
        return newparams

    (client_id,
     client_secret,
     redirect_uri,
     auth_base_url,
     token_url,
     grant_type,
     state) = itemgetter('appId', 'appKey', 'redirect_uri', 'auth_base_url',
                         'token_url', 'grant_type', 'state')(auth)

    authcode: Optional[str] = _get_auth_code(auth)
    if not authcode:
        logging.error('authcode is None')
        return None

    # construct request
    url: str = urllib.parse.urljoin(auth_base_url, token_url)
    params: Dict = {'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': grant_type,
                    'code': authcode,
                    'state': state}
    if refresh:
        params = _auth_refresh_token(params, refresh)

    response: requests.Response = requests.post(url, data=params)
    if response.status_code != 200:
        logging.error('error response %s', response)
        return None
    return response.json()

###################
#  cenerate sign  #
###################


def _gen_sign(auth: AuthData, token: Optional[TokenResult]) -> Optional[str]:
    if not token:
        return None

    access_token: str = token['access_token']
    appId, appKey = itemgetter('appId', 'appKey')(auth)

    # read Aqara doc about how to construct sign.
    sign_dict: Dict = {'accesstoken': access_token, 'appid': appId, 'time': str(currentTimestamp(13))}
    sign: str = md5((urllib.parse.urlencode(sign_dict).lower() + '&' + appKey).encode('ascii')).hexdigest()
    return sign


def _gen_header(auth: AuthData, token: Optional[TokenResult], sign: Optional[str]) -> Optional[Dict]:
    if not token:
        logging.error('token is None')
        return None
    if not sign:
        logging.error('sign is None')
        return None

    access_token: str = token['access_token']
    appId: str = auth['appId']
    return {'Accesstoken': access_token,
            'Appid': appId,
            'Content-Type': 'application/json;charset=UTF-8',
            'Sign': sign,
            'Time': str(currentTimestamp(13))}


#####################
#  query functions  #
#####################


def _get_pos(auth: AuthData,
             token: Optional[TokenResult],
             params: PosParam = {}) -> Optional[PosResult]:

    (api_query_base_url, api_query_pos_url) = itemgetter('api_query_base_url',
                                                         'api_query_pos_url')(auth)
    if not token:
        logging.error('token is None')
        return None

    sign: Optional[str] = _gen_sign(auth, token)
    headers: Optional[Dict] = _gen_header(auth, token, sign if sign is not None else None)

    url: str = urllib.parse.urljoin(api_query_base_url, api_query_pos_url)
    response: requests.Response = requests.get(url, data=cast(Dict, params), headers=headers)

    if response.status_code != 200:
        logging.error('error response %s', response)
        return None
    return response.json()['result']


def _get_device(auth: AuthData,
                token: Optional[TokenResult],
                params: DeviceParam = {}) -> Optional[DeviceResult]:

    (api_query_base_url, api_query_pos_url) = itemgetter('api_query_base_url',
                                                         'api_query_dev_url')(auth)

    if not token:
        logging.error('token is None')
        return None

    sign: Optional[str] = _gen_sign(auth, token)
    headers: Optional[Dict] = _gen_header(auth, token, sign if sign is not None else None)

    url: str = urllib.parse.urljoin(api_query_base_url, api_query_pos_url)
    response: requests.Response = requests.get(url, data=cast(Dict, params), headers=headers)

    if response.status_code != 200:
        logging.error('error response %s', response)
        return None
    return response.json()['result']


def _get_resource(auth: AuthData,
                  token: Optional[TokenResult],
                  params: ResourceParam) -> Optional[ResourceResult]:

    (api_query_base_url, api_query_resrouce_url) = itemgetter('api_query_base_url',
                                                              'api_query_resrouce_url')(auth)
    if not token:
        logging.error('token is None')
        return None

    sign: Optional[str] = _gen_sign(auth, token)
    headers: Optional[Dict] = _gen_header(auth, token, sign if sign is not None else None)

    url: str = urllib.parse.urljoin(api_query_base_url, api_query_resrouce_url)
    response: requests.Response = requests.post(url, json=cast(Dict, params), headers=headers)

    if response.status_code != 200:
        logging.error('error response %s', response)
        return None
    return response.json()['result']






