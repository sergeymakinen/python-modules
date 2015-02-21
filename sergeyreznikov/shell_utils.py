from __future__ import print_function, unicode_literals

import codecs
import dateutil.tz
import ntpath
import os
import re
import subprocess
import sys
import urllib2
from Cookie import SimpleCookie
from datetime import datetime


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
        exts = ['.com', '.exe', '.bat', '.cmd']
        if shell:
            exts += [ext for ext in os.environ.get('PATHEXT', '').lower().split(os.pathsep) if ext not in exts]
        if os.path.splitext(name)[1].lower() not in exts:
            names = []
        names += [name + ext for ext in exts]
    for path in pathes:
        for name in names:
            probe_path = os.path.join(path, name)
            if os.path.isfile(probe_path):
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


def get_keychain_password(account):
    output = subprocess.Popen(['security', 'find-generic-password', '-g', '-a', account],
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
        if os.path.isfile(path):
            return os.path.realpath(path)

        exec_path = find_executable(path, shell)
        if exec_path is not None:
            return os.path.realpath(exec_path)

    return os.path.realpath(os.path.expandvars(os.path.expanduser(path)))


def retrieve_file(url, file_path=None, user_agent=None, cookies=None, referer=None, xhr=False):
    opener = urllib2.build_opener()
    if user_agent is not None:
        opener.addheaders = [('User-Agent', user_agent)]
    if cookies:
        simple_cookie = SimpleCookie()
        for cookie in cookies:
            simple_cookie[str(cookie)] = cookies[cookie]
        opener.addheaders.append(('Cookie', simple_cookie.output(header='', sep=';')[1:]))
    if referer is not None:
        opener.addheaders.append(('Referer', referer))
    if xhr:
        opener.addheaders.append(('X-Requested-With', 'XMLHttpRequest'))
    resp = opener.open(url)
    if file_path is not None:
        file_obj = open(file_path, 'wb')
        while True:
            resp_buffer = resp.read(8192)
            if buffer is None:
                break

            file_obj.write(resp_buffer)
        file_obj.close()
        resp.close()
    else:
        content = resp.read()
        resp.close()
        return content


def safe_file_name(name, posix=None):
    if posix is None:
        posix = sys.platform != 'win32'
    if posix:
        return re.sub(r'[\x00/]', '', name)
    else:
        name = re.sub(r'[\x00-\x1f<>:"/\|?*]', '', name).rstrip('. ')[:255]
        if ntpath.splitext(name)[0].lower() in [
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
        ]:
            name = ''
        return name


def set_keychain_password(account, service, password, label=None, prompt=False):
    if label is None:
        label = '{0} {1}'.format(account, service)
    cmd = ['security', 'add-generic-password', '-a', account, '-s', service, '-w', password, '-l', label]
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


def touch(path, times=None):
    if not os.path.exists(path):
        open(path, 'a').close()
        if times is None:
            return
    os.utime(path, times)
