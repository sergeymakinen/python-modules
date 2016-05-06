import http.cookiejar
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from calendar import timegm
from collections import OrderedDict
from configparser import ConfigParser
from datetime import datetime
from time import gmtime

from dateutil.tz import tzlocal, tzutc
from dateutil.zoneinfo import gettz

TIME_FORMAT_ISO9075 = '%Y-%m-%d %H:%M:%S'

WIN32_BAD_NAMES = [
    'aux',
    'com1',
    'com2',
    'com3',
    'com4',
    'com5',
    'com6',
    'com7',
    'com8',
    'com9',
    'con',
    'lpt1',
    'lpt2',
    'lpt3',
    'lpt4',
    'lpt5',
    'lpt6',
    'lpt7',
    'lpt8',
    'lpt9',
    'nul',
    'prn'
]

WIN32_X_EXTS = [
    '.com',
    '.exe',
    '.bat',
    '.cmd'
]


class ConfigError(Exception):
    pass


def error(message, code=1):
    """
    :param str message: message
    :param int code: code
    """

    sys.stdout.flush()
    print(message, file=sys.stderr)
    sys.exit(code)


def exec_file(path, globals=None, locals=None):
    if globals is None:
        globals = sys._getframe(1).f_globals
    if locals is None:
        locals = sys._getframe(1).f_locals
    with open(path, 'r') as file_obj:
        exec(compile(file_obj.read(), path, 'exec'), globals, locals)


def find_executable(name, shell=False):
    """
    :param str name: name
    :param bool shell: shell
    :return str: str
    """

    pathes = os.environ.get('PATH', os.defpath).split(os.pathsep)
    names = [name]
    if sys.platform == 'win32':
        if os.curdir not in pathes:
            pathes.insert(0, os.curdir)
        exts = WIN32_X_EXTS
        if shell:
            exts += [ext for ext in os.environ.get('PATHEXT', '').lower().split(os.pathsep) if ext not in exts]
        if os.path.splitext(name)[1].lower() not in exts:
            names = []
        names += [name + ext for ext in exts]
    for path in pathes:
        for name in names:
            probe_path = os.path.join(path, name)
            if os.path.isfile(probe_path) and os.access(probe_path, os.X_OK):
                return probe_path


def format_size(size):
    """
    :param float size: size
    :return str: str
    """

    size = float(size)
    unit = 'TB'
    for current_unit in ['bytes', 'KB', 'MB', 'GB']:
        if size < 1024:
            unit = current_unit
            break
        size /= 1024
    return '{0:.2f}'.format(size).rstrip('0').rstrip('.') + ' ' + unit


def get_keychain_password(service, account):
    output = subprocess.Popen(['security', 'find-generic-password', '-g', '-s', service, '-a', account],
                              universal_newlines=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[1]
    matches = re.search(r'^password: (?:0x([0-9A-F]+)\s*)?"(.*)"$', output)
    if matches:
        hex_password, string_password = matches.groups()
        if hex_password:
            password = eval('"' + re.sub('(..)', r'\x\1', hex_password) + '"')
            if '' in password:
                password = password[:password.index('')]
            return password
        else:
            return string_password


def import_config(file_name=None, suffix='.ini', osx_domain='ru.makinen', python_config_globals=None):
    """
    :param str file_name: file_name
    :param str suffix: suffix
    :param str osx_domain: osx_domain
    :param dict python_config_globals: python_config_globals
    :return OrderedDict: OrderedDict
    """
    if file_name is None:
        if not hasattr(sys.modules['__main__'], '__file__'):
            raise ConfigError("can't guess a file_name parameter")
        file_name = os.path.splitext(os.path.basename(sys.modules['__main__'].__file__))[0]
    file_name = os.path.normpath(file_name)
    probe_file_names = []
    if all(sep not in file_name for sep in [os.path.sep, str(os.path.altsep)]):
        if hasattr(sys.modules['__main__'], '__file__'):
            probe_file_name = os.path.join(os.path.dirname(sys.modules['__main__'].__file__), file_name + suffix)
            if probe_file_name != sys.modules['__main__'].__file__:
                probe_file_names.append(probe_file_name)
        if sys.platform == 'darwin':
            native_name = '.'.join([osx_domain, ''.join(part.capitalize() for part in file_name.split('-'))])
            probe_file_names.append(os.path.join(os.path.expanduser('~/Library/Preferences'),
                                    native_name + suffix))
            probe_file_names.append(os.path.join('/Library/Preferences', native_name + suffix))
        elif sys.platform == 'win32':
            native_name = ' '.join(part.capitalize() for part in file_name.split('-'))
            probe_file_names.append(os.path.join(os.path.expandvars(r'%APPDATA%\Roaming'),
                                    native_name + suffix))
        if sys.platform != 'win32':
            probe_file_names.append(os.path.join(os.path.expanduser('~/.config'), file_name))
            probe_file_names.append(os.path.join('/usr/local/etc', file_name))
            probe_file_names.append(os.path.join('/etc', file_name))
    else:
        probe_file_names.append(os.path.abspath(file_name))
    for path in probe_file_names:
        if os.path.isfile(path):
            if suffix == '.ini':
                parser = ConfigParser()
                parser.read(path, 'utf-8')
                return parser._sections
            elif suffix == '.json':
                with open(path, 'r') as file_obj:
                    return json.load(file_obj, object_hook=OrderedDict)
            elif suffix == '.py':
                config_locals = OrderedDict()
                exec_file(path, python_config_globals, config_locals)
                return config_locals
            else:
                raise ConfigError('unknown config suffix: ' + suffix)
    raise ConfigError("can't find a config file, expected one of:\n" + '\n'.join(probe_file_names))


def input_bool(question, default=None):
    """
    :param str question: question
    :param bool default: default
    :return bool: bool
    """

    if default is None:
        question += ' [y/n]? '
    elif default:
        question += ' [Y/n]? '
    else:
        question += ' [y/N]? '
    while True:
        answer = input(question).lower()
        if answer == '':
            if default is None:
                print('Incorrect answer.')
                continue
            else:
                return default
        else:
            return answer in ['y', 'yes']


def log(path, message):
    """
    :param str path: path
    :param str message: message
    :return:
    """

    if os.path.isfile(path):
        file_obj = open(path, 'a', encoding='utf8')
        file_obj.write(message + os.linesep)
        file_obj.close()


def realpath(path, executable=False, shell=False):
    """
    :param str path: path
    :param bool executable: executable
    :param bool shell: shell
    :return str: str
    """

    if executable:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return os.path.realpath(path)

        exec_path = find_executable(path, shell)
        if exec_path is not None:
            return os.path.realpath(exec_path)

    return os.path.realpath(os.path.expandvars(os.path.expanduser(path)))


def retrieve_file(url, file_path=None,
                  user_agent=None, cookies=None, referer=None, xhr=False, post_data=None,
                  include_metadata=False, encoding='utf-8'):
    """
    :param str url: url
    :param str file_path: file_path
    :param str user_agent: user_agent
    :param dict cookies: cookies
    :param str referer: referer
    :param bool xhr: xhr
    :param dict|str post_data: post_data
    :param bool include_metadata: include_metadata
    :param str encoding: encoding
    :return str|bytes|dict: str|bytes|dict
    """

    cookie_jar = http.cookiejar.CookieJar()
    if cookies is not None:
        domain = urllib.parse.urlparse(url).netloc
        for cookie in cookies:
            cookie_params = {
                'version': 1,
                'name': cookie,
                'port': None,
                'port_specified': False,
                'domain': domain,
                'domain_specified': False,
                'domain_initial_dot': False,
                'path': '/',
                'path_specified': False,
                'secure': False,
                'expires': None,
                'discard': False,
                'comment': None,
                'comment_url': None,
                'rest': {},
                'rfc2109': False
            }
            if isinstance(cookies[cookie], dict):
                cookie_params.update(cookies[cookie])
            else:
                cookie_params['value'] = cookies[cookie]
            cookie_jar.set_cookie(http.cookiejar.Cookie(**cookie_params))
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    if user_agent is not None:
        opener.addheaders = [('User-Agent', user_agent)]
    if referer is not None:
        opener.addheaders.append(('Referer', referer))
    if xhr:
        opener.addheaders.append(('X-Requested-With', 'XMLHttpRequest'))
    if isinstance(post_data, dict):
        post_data = urllib.parse.urlencode(post_data)
    if isinstance(post_data, str) and encoding is not None:
        post_data = post_data.encode(encoding)
    resp = opener.open(url, post_data)
    if include_metadata:
        result = {
            'url': resp.geturl(),
            'status_code': resp.getcode(),
            'headers': []
        }
        for header in resp.info().headers:
            result['headers'].append(tuple([value.strip() for value in header.split(':', 1)]))
    else:
        result = None
    if file_path is not None:
        file_obj = open(file_path, 'wb')
        while True:
            resp_buffer = resp.read(8192)
            if len(resp_buffer) == 0:
                break

            file_obj.write(resp_buffer)
        file_obj.close()
        resp.close()
    else:
        content = resp.read()
        if encoding is not None:
            content = content.decode(encoding)
        if include_metadata:
            result['content'] = content
        else:
            result = content
        resp.close()
    return result


def safe_file_name(name, posix=None):
    """
    :param str name: name
    :param bool posix: posix
    :return str: str
    """

    if posix is None:
        posix = sys.platform != 'win32'
    if posix:
        return re.sub(r'[\x00/]', '', name)
    else:
        name = re.sub(r'[\x00-\x1f<>:"/\|?*]', '', name).rstrip('. ')[:255]
        if os.path.splitext(name)[0].lower() in WIN32_BAD_NAMES:
            name = ''
        return name


def set_keychain_password(service, account, password, label=None, prompt=False):
    if label is None:
        label = '{0} {1}'.format(service, account)
    cmd = ['security', 'add-generic-password', '-s', service, '-a', account, '-w', password, '-l', label]
    if prompt:
        cmd += ['-T', '']
    subprocess.check_call(cmd)


def set_time_tz(time, tz='local'):
    """
    :param datetime time: time
    :param str tz: tz
    :return datetime: datetime
    """

    if time.utcoffset() is None:
        if tz == 'local':
            tz = tzlocal()
        elif tz == 'UTC':
            tz = tzutc()
        else:
            tz = gettz(tz)
        time = time.replace(tzinfo=tz)
    return time


def strftime(format, timestamp_or_datetime=None, tz='local'):
    """
    :param str format: format
    :param int|datetime timestamp_or_datetime: timestamp_or_datetime
    :param str tz: tz
    :return str: str
    """

    if tz == 'local':
        tz = tzlocal()
    elif tz == 'UTC':
        tz = tzutc()
    else:
        tz = gettz(tz)
    if timestamp_or_datetime is None:
        time = datetime.now(tz)
    elif isinstance(timestamp_or_datetime, int):
        time = datetime.fromtimestamp(timestamp_or_datetime, tz)
    elif isinstance(timestamp_or_datetime, datetime):
        if timestamp_or_datetime.utcoffset() is None:
            time = timestamp_or_datetime
        else:
            time = timestamp_or_datetime.astimezone(tz)
    else:
        raise TypeError('timestamp_or_datetime should be int or datetime.datetime')
    return time.strftime(format)


def strptime(format, string, tz='local'):
    """
    :param str format: format
    :param str string: string
    :param str tz: tz
    :return datetime: datetime
    """

    return set_time_tz(datetime.strptime(string, format), tz)


def timestamp():
    return timegm(gmtime())


def touch(path, times=None):
    """
    :param str path: path
    :param tuple(float, float) times: times
    """

    if not os.path.exists(path):
        open(path, 'a').close()
        if times is None:
            return
    os.utime(path, times)
