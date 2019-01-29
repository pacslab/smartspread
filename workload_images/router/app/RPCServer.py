"""
A Scalable and threaded Consumer that will automatically re-connect on failure.
"""
import logging
import threading
import time

import amqpstorm
from amqpstorm import Connection
from amqpstorm import Message

import RabbitServerInfo as info

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
LOGGER = logging.getLogger(__name__)


class ScalableRpcServer(object):
    def __init__(self, hostname='127.0.0.1',
                 username='guest', password='guest', heartbeat=10,
                 rpc_queue='rpc_queue', queue_args=info.args,
                 number_of_consumers=5, max_retries=None, url='http://nmahmoudi.ir/'):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.rpc_queue = rpc_queue
        self.number_of_consumers = number_of_consumers
        self.max_retries = max_retries
        self._connection = None
        self._consumers = []
        self._stopped = threading.Event()
        self.heartbeat = heartbeat
        self.url = url

        self.queue_args = queue_args

    def start_server(self):
        """Start the RPC Server.
        :return:
        """
        self._stopped.clear()
        if not self._connection or self._connection.is_closed:
            self._create_connection()
        while not self._stopped.is_set():
            try:
                # Check our connection for errors.
                self._connection.check_for_errors()
                self._update_consumers()
            except amqpstorm.AMQPError as why:
                # If an error occurs, re-connect and let update_consumers
                # re-open the channels.
                LOGGER.warning(why)
                self._stop_consumers()
                self._create_connection()
            time.sleep(1)

    def increase_consumers(self):
        """Add one more consumer.
        :return:
        """
        if self.number_of_consumers <= 20:
            self.number_of_consumers += 1

    def decrease_consumers(self):
        """Stop one consumer.
        :return:
        """
        if self.number_of_consumers > 0:
            self.number_of_consumers -= 1

    def stop(self):
        """Stop all consumers.
        :return:
        """
        while self._consumers:
            consumer = self._consumers.pop()
            consumer.stop()
        self._stopped.set()
        self._connection.close()

    def _create_connection(self):
        """Create a connection.
        :return:
        """
        attempts = 0
        while True:
            attempts += 1
            if self._stopped.is_set():
                break
            try:
                self._connection = Connection(self.hostname,
                                              self.username,
                                              self.password,
                                              heartbeat=self.heartbeat)
                break
            except amqpstorm.AMQPError as why:
                LOGGER.warning(why)
                if self.max_retries and attempts > self.max_retries:
                    raise Exception('max number of retries reached')
                time.sleep(min(attempts * 2, 30))
            except KeyboardInterrupt:
                break

    def _update_consumers(self):
        """Update Consumers.
            - Add more if requested.
            - Make sure the consumers are healthy.
            - Remove excess consumers.
        :return:
        """
        # Do we need to start more consumers.
        consumer_to_start = \
            min(max(self.number_of_consumers - len(self._consumers), 0), 2)
        for _ in range(consumer_to_start):
            consumer = Consumer(self.rpc_queue, queue_args=self.queue_args, url=self.url)
            self._start_consumer(consumer)
            self._consumers.append(consumer)

        # Check that all our consumers are active.
        for consumer in self._consumers:
            if consumer.active:
                continue
            self._start_consumer(consumer)
            break

        # Do we have any overflow of consumers.
        self._stop_consumers(self.number_of_consumers)

    def _stop_consumers(self, number_of_consumers=0):
        """Stop a specific number of consumers.
        :param number_of_consumers:
        :return:
        """
        while len(self._consumers) > number_of_consumers:
            consumer = self._consumers.pop()
            consumer.stop()

    def _start_consumer(self, consumer):
        """Start a consumer as a new Thread.
        :param Consumer consumer:
        :return:
        """
        thread = threading.Thread(target=consumer.start,
                                  args=(self._connection,))
        thread.daemon = True
        thread.start()


import socket
from worker_helper import convert_to_json, load_from_json
from urllib.parse import urlparse
import http.client as client


class Consumer(object):
    def __init__(self, rpc_queue, url='http://nmahmoudi.ir/', queue_args=info.args, **kwargs):
        self.rpc_queue = rpc_queue
        self.channel = None
        self.active = False

        self.queue_args = queue_args

        self.url = url
        self.o = urlparse(self.url)
        self.host = self.o.netloc
        if self.o.path == '/':
            self.path = ''
        else:
            self.path = self.o.path

        self.timeout = kwargs.pop('timeout', 5)

        if self.o.scheme == 'https':
            self.conn = client.HTTPSConnection(self.host, timeout=self.timeout)
        else:
            self.conn = client.HTTPConnection(self.host, timeout=self.timeout)

    def start(self, connection):
        self.channel = None
        try:
            self.active = True
            self.channel = connection.channel(rpc_timeout=10)
            self.channel.basic.qos(prefetch_count=1)
            self.channel.queue.declare(self.rpc_queue, arguments=self.queue_args)
            self.channel.basic.consume(self, self.rpc_queue, no_ack=False)
            self.channel.start_consuming()
            if not self.channel.consumer_tags:
                # Only close the channel if there is nothing consuming.
                # This is to allow messages that are still being processed
                # in __call__ to finish processing.
                self.channel.close()
        except amqpstorm.AMQPError:
            pass
        finally:
            self.active = False

    def stop(self):
        if self.channel:
            self.channel.close()

    def __call__(self, message):
        """Process the RPC Payload.
        :param Message message:
        :return:
        """
        b = load_from_json(message.body)
        print(" [.] request(%s)" % b)

        try:
            self.conn.request("GET", self.path + b)
            r = self.conn.getresponse()
            body = r.read()
            ret = {
                'stat': r.status,
                'body': body,
                'headers': r.getheaders(),
            }
        except TimeoutError:
            ret = {
                'stat': 504,
                'body': '504 Gateway Timeout',
                'headers': '',
            }
        except socket.timeout:
            ret = {
                'stat': 504,
                'body': '504 Gateway Timeout',
                'headers': '',
            }
        except client.RemoteDisconnected:
            time.sleep(0.1)
            return self.__call__(message)
        except ConnectionResetError:
            ret = {
                'stat': 503,
                'body': '503 Bad Gateway',
                'headers': '',
            }
        except client.CannotSendRequest:
            time.sleep(.1)
            if self.o.scheme == 'https':
                self.conn = client.HTTPSConnection(self.host, timeout=self.timeout)
            else:
                self.conn = client.HTTPConnection(self.host, timeout=self.timeout)
            time.sleep(.1)
            return self.__call__(message=message)

        response = convert_to_json(ret)

        properties = {
            'correlation_id': message.correlation_id
        }

        response = Message.create(message.channel, response, properties)
        response.publish(message.reply_to)

        message.ack()


if __name__ == '__main__':
    import argparse
    import os

    parser = argparse.ArgumentParser(description='Start a RPC server with a url and a queue name.')
    info.add_arguments(parser)
    parser.add_argument('-c', '--num-consumers', type=int, nargs='?',
                        help='The number of parallel consumers.',
                        default=5)

    args = parser.parse_args()

    queue_args = info.args
    queue_args['x-max-length'] = args.max_length
    queue_args['x-message-ttl'] = args.message_ttl

    print(args)

    postfix = ""
    if 'postfix' in os.environ:
        p = os.environ['postfix']
        if p != "n/a":
            postfix = p

    print('postfix: ', postfix)

    RPC_SERVER = ScalableRpcServer(args.rmq_server, args.rmq_user, args.rmq_pass, int(args.heartbeat),
                                   args.queue + postfix, url=args.website, queue_args=queue_args, number_of_consumers=args.num_consumers)
    RPC_SERVER.start_server()
