"""
utils for discovery cluster
"""
from distutils.version import StrictVersion
from django.utils.encoding import smart_text
import re
from telnetlib import Telnet


class WrongProtocolData(ValueError):
    """
    Exception for raising when we get something unexpected
    in telnet protocol
    """
    def __init__(self, cmd, response):
        super(WrongProtocolData, self).__init__(
            'Unexpected response {0} for command {1}'.format(response, cmd))


def get_cluster_info(host, port, discovery_timeout, ignore_cluster_errors=False):
    """
    return dict with info about nodes in cluster and current version
    {
        'nodes': [
            'IP:port',
            'IP:port',
        ],
        'version': '1.4.4'
    }
    """
    if discovery_timeout:
        client = Telnet(host, int(port), timeout=discovery_timeout)
    else:  # use telnet's default timeout (socket._GLOBAL_DEFAULT_TIMEOUT)
        client = Telnet(host, int(port))
    client.write(b'version\n')
    res = client.read_until(b'\r\n').strip()
    version_list = res.split(b' ')
    if len(version_list) not in [2, 3] or version_list[0] != b'VERSION':
        raise WrongProtocolData('version', res)
    version = version_list[1]
    if StrictVersion(smart_text(version)) >= StrictVersion('1.4.14'):
        cmd = b'config get cluster\n'
    else:
        cmd = b'get AmazonElastiCache:cluster\n'
    client.write(cmd)
    # note expect() does not use the client's socket timeout by default
    regex_index, match_object, res = client.expect([
        re.compile(b'\n\r\nEND\r\n'),
        re.compile(b'ERROR\r\n')
    ], timeout=discovery_timeout)
    client.close()

    if res == b'ERROR\r\n' and ignore_cluster_errors:
        return {
            'version': version,
            'nodes': [
                '{0}:{1}'.format(smart_text(host),
                               smart_text(port))
            ]
        }

    ls = list(filter(None, re.compile(br'\r?\n').split(res)))
    if len(ls) != 4:
        raise WrongProtocolData(cmd, res)

    try:
        version = int(ls[1])
    except ValueError:
        raise WrongProtocolData(cmd, res)
    nodes = []
    try:
        for node in ls[2].split(b' '):
            host, ip, port = node.split(b'|')
            nodes.append('{0}:{1}'.format(smart_text(ip or host),
                                        smart_text(port)))
    except ValueError:
        raise WrongProtocolData(cmd, res)
    return {
        'version': version,
        'nodes': nodes
    }
