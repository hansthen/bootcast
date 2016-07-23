# vim: tabstop=4 softtabstop=0 expandtab shiftwidth=4 smarttab
import socket
import struct
import os
from threading import Thread, Event
from contextlib import closing
import logging
from time import sleep
import tornado.ioloop
import tornado.web
from uuid import uuid1
from collections import namedtuple
import argparse


logging.basicConfig()
logger = logging.getLogger(__file__)


Cast = namedtuple('Cast', ['app', 'filename', 'stop', 'counter',
                           'pages', 'address', 'port', 'clients'])


def broadcast(cast):
    """Broadcast the file"""
    cast.app.casts[cast.filename] = cast
    page_size = cast.app.args.page_size
    throttle = cast.app.args.throttle
    filename = cast.filename
    total = cast.pages
    stop = cast.stop
    counter = cast.counter
    counter.counter = 0

    logger.debug("start broadcast of %s", filename)
    logger.debug("%d pages" % total)

    # This is ugly but keeps flake8 from complaining
    with open(filename) as f, closing(socket.socket(socket.AF_INET,
                                      socket.SOCK_DGRAM)) as sock:

        # Setup the multicast socket
        group = socket.inet_aton(cast.address)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        loop = 0
        while not stop.is_set():
            logger.debug("Starting loop %d %d", loop, counter.counter)
            loop += 1
            page = 0
            f.seek(0)
            data = f.read(page_size)

            if counter.is_set():
                logger.debug('reset inactivity counter %d' % loop)
                counter.counter = 0
                counter.clear()
            else:
                counter.counter += 1

            if counter.counter > 5:
                stop.set()

            while data:
                if stop.is_set():
                    logger.debug('shutting down thread in loop %d' % loop)
                    break

                page += 1
                check = checksum(data)
                msg = struct.pack('!IIII%ds' % len(data), page, total,
                                  check, len(data), data)
                # logger.debug("sending page %d[%d]" % (page, len(data)))
                sock.sendto(msg, (cast.address, cast.port))
                data = f.read(page_size)
                sleep(throttle)
        del cast.app.casts[filename]


def checksum(st):
    """Calculate a checksum over the pages"""
    return reduce(lambda x, y: x+y, map(ord, st)) % 256


class JoinHandler(tornado.web.RequestHandler):
    """Handle a join request"""
    def get(self, path):
        broadcasts = self.application.casts
        args = self.application.args
        client = intern(uuid1().hex)
        page_size = args.page_size
        path = os.path.join(args.dir, path)
        if not os.path.exists(path):
            raise tornado.web.HTTPError(status_code=404,
                                        log_message="Path %s not found" % path)
        pages = os.path.getsize(path) / page_size + 1

        # if the cast is alreay running attach client
        if path in broadcasts:
            cast = broadcasts[path]
            cast.clients.append(client)
            cast.counter.set()
        # if the cast is not running start it first
        else:
            address = args.group
            port = args.start + len(broadcasts)
            cast = Cast(self.application, path, Event(), Event(),
                        pages, address, port, [client])
            t = Thread(target=broadcast, args=(cast,))
            t.start()

        # send connection data to the client
        self.write("CONNECT=%s:%d\n" % (cast.address, cast.port))
        self.write("TOKEN=%s\n" % (client))
        self.write("PAGES=%d\n" % (pages))
        self.write("PAGESIZE=%d\n" % (page_size))
        self.write("\n")


class LeaveHandler(tornado.web.RequestHandler):
    """Handles a leave request"""
    def get(self, path):
        token = intern(self.request.headers.get('X-TOKEN'))
        casts = self.application.casts
        logger.debug("removing client %s", token)
        path = os.path.join(args.dir, path)
        if path in casts:
            cast = casts[path]
            clients = cast.clients
            clients.remove(token)
            cast.counter.set()
            if not clients:
                # stop the broadcast
                cast.stop.set()
                logger.debug("stop broadcast %s", path)
            else:
                pass
        else:
            logger.error("Received leave request from unknown broadcast %s",
                         path)


def make_app():
    return tornado.web.Application([
        (r"/join/(.*)", JoinHandler),
        (r"/leave/(.*)", LeaveHandler),
    ])

parser = argparse.ArgumentParser(description="Start a file caster")
parser.add_argument('--dir', help="the directory from which files are served",
                    default='')
parser.add_argument('--page-size', '-s', type=int,
                    help="the page size", default=1450)
parser.add_argument('--ip',
                    help="the listener ip address", default='')
parser.add_argument('--port', '-p', type=int,
                    help="the listening port", default=8888)
parser.add_argument('--group',
                    help="the multicast address", default='224.3.29.71')
parser.add_argument('--start', type=int,
                    help="the start port for data groups", default=12000)
parser.add_argument('--throttle', type=float,
                    help="the delay between sending data packets in ms",
                    default=0.1)

loglevels = [key for key in logging._levelNames if isinstance(key, str)]
parser.add_argument('--logLevel', choices=loglevels, default='INFO')

if __name__ == '__main__':
    args = parser.parse_args()
    app = make_app()
    app.casts = {}
    app.args = args
    app.listen(args.port)
    logger.setLevel(args.logLevel)
    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        for value in app.casts.itervalues():
            value.stop.set()
