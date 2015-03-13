from __future__ import print_function, unicode_literals

import codecs
import cookielib
import dateutil.tz
import os
import re
import subprocess
import sys
import urllib2
from calendar import timegm
from datetime import datetime
from time import gmtime
from urlparse import urlparse

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


def error(message, code=1):
    sys.stdout.flush()
    print(message, file=sys.stderr)
    sys.exit(code)


def find_executable(name, shell=False):
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


def input_bool(question, default=None):
    if default is None:
        question += ' [y/n]? '
    elif default:
        question += ' [Y/n]? '
    else:
        question += ' [y/N]? '
    while True:
        answer = raw_input(question).lower()
        if answer == '':
            if default is None:
                print('Incorrect answer.')
                continue
            else:
                return default
        else:
            return answer in ['y', 'yes']


def log(path, message):
    if os.path.isfile(path):
        file_obj = codecs.open(path, 'a', 'utf8')
        file_obj.write(message + os.linesep)
        file_obj.close()


def realpath(path, executable=False, shell=False):
    if executable:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return os.path.realpath(path)

        exec_path = find_executable(path, shell)
        if exec_path is not None:
            return os.path.realpath(exec_path)

    return os.path.realpath(os.path.expandvars(os.path.expanduser(path)))


def retrieve_file(url, file_path=None, user_agent=None, cookies=None, referer=None, xhr=False, include_metadata=False):
    cookie_jar = cookielib.CookieJar()
    if cookies is not None:
        domain = urlparse(url).netloc
        for cookie in cookies:
            cookie_params = {
                'version': None,
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
            cookie_jar.set_cookie(cookielib.Cookie(**cookie_params))
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    if user_agent is not None:
        opener.addheaders = [('User-Agent', user_agent)]
    if referer is not None:
        opener.addheaders.append(('Referer', referer))
    if xhr:
        opener.addheaders.append(('X-Requested-With', 'XMLHttpRequest'))
    resp = opener.open(url)
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
        if include_metadata:
            result['content'] = resp.read()
        else:
            result = resp.read()
        resp.close()
    return result


def safe_file_name(name, posix=None):
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


def strftime(format, timestamp=None, local=True):
    if local:
        tz = dateutil.tz.tzlocal()
    else:
        tz = dateutil.tz.tzutc()
    if timestamp is None:
        return datetime.now(tz).strftime(format)
    else:
        return datetime.fromtimestamp(timestamp, tz).strftime(format)


def timestamp():
    return timegm(gmtime())


def touch(path, times=None):
    if not os.path.exists(path):
        open(path, 'a').close()
        if times is None:
            return
    os.utime(path, times)
