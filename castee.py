# vim: tabstop=4 softtabstop=0 expandtab shiftwidth=4 smarttab
import socket
import sys
import struct
import requests
import logging
import argparse

logging.basicConfig()
logger = logging.getLogger(__file__)


def main(args):
    # Join the cast
    r = requests.get(args.url)
    if r.status_code != 200:
        logger.error(r.text)
        sys.exit(1)

    # Parse the connection data
    parms = {}
    for line in r.text.split('\n'):
        if not line.strip():
            continue
        key, value = line.split('=', 1)
        parms[key] = value

    mcast, port = parms['CONNECT'].split(':')
    port = int(port)
    pages = int(parms['PAGES'])
    page_size = int(parms['PAGESIZE'])
    token = parms['TOKEN']

    # Create the data socket
    logger.debug("setup data socket %s:%d" % (mcast, port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    sock.bind((mcast, port))
    sock.settimeout(5)

    # Keep track of all pages
    missing = [j for j in range(1, pages + 1)]

    # Main data loop
    with open(args.out, 'w') as f:
        while True:
            header_size = struct.calcsize('!IIII')
            data = sock.recv(header_size+page_size)
            i, total, checksum, size = struct.unpack('!IIII',
                                                     data[:header_size])
            data = struct.unpack('!%ds' % size, data[header_size:])[0]
            if i not in missing:
                logger.debug("Received duplicate page, missing %d",
                             len(missing))
            else:
                f.seek((i - 1) * page_size)
                f.write(data)
                logger.debug("Received page %d of %d", i, pages)
                missing.remove(i)

            # If we have all pages, send a leave request and exit loop
            if not missing:
                logger.debug("All pages received")
                r = requests.get(args.url.replace('join', 'leave', 1),
                                 headers={'X-TOKEN': token})
                break

# setup command line arguments
parser = argparse.ArgumentParser(description="Request a filecast")
parser.add_argument('url', help="the file to be downloaded")
parser.add_argument('-O', '--out', metavar="OUTPUT FILE",
                    help="the output filename", default='out')
loglevels = [key for key in logging._levelNames if isinstance(key, str)]
parser.add_argument('--logLevel', choices=loglevels, default='INFO')


if __name__ == '__main__':
    args = parser.parse_args()
    logger.setLevel(args.logLevel)
    main(args)
