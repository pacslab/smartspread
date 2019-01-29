import time

from worker_helper import convert_to_json, load_from_json
import RabbitServerInfo as info

import threading
import logging
import amqpstorm
from amqpstorm import Message

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
LOGGER = logging.getLogger(__name__)


class RpcClient(object):
    """Asynchronous Rpc client."""

    def __init__(self, host, username, password, rpc_queue, max_retries=None, timeout=info.QUEUE_TIMEOUT):
        self.timeout = timeout
        self.queue = {}
        self.host = host
        self.username = username
        self.password = password
        self.channel = None
        self.connection = None
        self.callback_queue = None
        self.rpc_queue = rpc_queue
        self.max_retries = max_retries
        self.connected = False
        self.open()

    def _create_connection(self):
        """Create a connection.
        :return:
        """
        attempts = 0
        while True:
            attempts += 1
            try:
                self.connection = amqpstorm.Connection(self.host,
                                                       self.username,
                                                       self.password,
                                                       heartbeat=60)
                break
            except amqpstorm.AMQPError as why:
                LOGGER.warning(why)
                if self.max_retries and attempts > self.max_retries:
                    raise Exception('max number of retries reached')
                time.sleep(min(attempts * 2, 30))
            except KeyboardInterrupt:
                break

    def open(self):
        """Open Connection."""
        self.create_connection()
        self._create_process_thread()

    def _create_process_thread(self):
        """Create a thread responsible for consuming messages in response
         to RPC requests.
        """
        thread = threading.Thread(target=self._process_connection_events)
        thread.setDaemon(True)
        thread.start()

        thread2 = threading.Thread(target=self._process_data_events)
        thread2.setDaemon(True)
        thread2.start()

    def create_connection(self):
        self._create_connection()

    def _process_connection_events(self):
        if not self.connection or self.connection.is_closed:
            self.create_connection()
        while True:
            try:
                # Check our connection for errors.
                self.connection.check_for_errors()
            except amqpstorm.AMQPError as why:
                # If an error occurs, re-connect and let update_consumers
                # re-open the channels.
                LOGGER.warning(why)
                self.channel.close()
                self.create_connection()
            time.sleep(1)

    def _process_data_events(self):
        """Process Data Events using the Process Thread."""
        # if not self.connection:
        #     self.create_connection()
        while True:
            if not self.connection:
                time.sleep(1)
                continue
            try:
                self.channel = self.connection.channel(rpc_timeout=5)
                result = self.channel.queue.declare(exclusive=True, auto_delete=True)
                self.callback_queue = result['queue']
                self.channel.confirm_deliveries()
                self.channel.basic.consume(self._on_response, no_ack=True,
                                           queue=self.callback_queue)
                self.connected = True
                self.channel.start_consuming()
                self.connected = False
                if not self.channel.consumer_tags:
                    self.channel.close()
            except amqpstorm.AMQPError as why:
                self.connected = False
                LOGGER.exception(why)
                self.create_connection()

    def _on_response(self, message):
        """On Response store the message with the correlation id in a local
         dictionary.
        """
        self.queue[message.correlation_id] = load_from_json(message.body)

    def send_request(self, payload, rpc_queue=None):
        if rpc_queue is None:
            rpc_queue = self.rpc_queue

        # Create the Message object.
        while self.connected is False:
            time.sleep(0.1)
        props = {
            'delivery_mode': 1,
        }
        message = Message.create(self.channel, payload, properties=props)
        message.reply_to = self.callback_queue

        # Create an entry in our local dictionary, using the automatically
        # generated correlation_id as our key.
        self.queue[message.correlation_id] = None

        # Publish the RPC request.
        res = False
        try:
            res = message.publish(routing_key=rpc_queue)
        except amqpstorm.AMQPError as why:
            LOGGER.exception(why)
            self.create_connection()

        # Return the Unique ID used to identify the request.
        return message.correlation_id, res

    def call(self, m, rpc_queue=None):
        if rpc_queue is None:
            rpc_queue = self.rpc_queue
        
        corr_id, res = self.send_request(convert_to_json(m), rpc_queue=rpc_queue)
        # Wait until we have received a response.

        if res is False:
            return {
                'stat': 503,
                'body': '503 Service Unavailable',
                'headers': '',
            }

        sleep_time = 10  # in ms
        timeout = self.timeout
        # timeout = 300
        timeout_count = int(timeout / sleep_time)
        counter = 0
        while self.queue[corr_id] is None:
            self.channel.check_for_errors()
            counter += 1
            if self.connected is False:
                print('disconnected!')
                time.sleep(0.5)
                return self.call(m)
            if counter > timeout_count:
                print("Response Timed Out!")
                return {
                    'stat': 504,
                    'body': '504 Gateway Timeout',
                    'headers': '',
                }
            time.sleep(sleep_time / 1000)

        # Return the response to the user.
        return self.queue[corr_id]


start_time = 0


def tic():
    global start_time
    start_time = time.time()


def toc():
    return (time.time() - start_time) * 1000


def toc_print():
    elapsed = (time.time() - start_time) * 1000
    print('{:4.02f} ms'.format(elapsed))
    return elapsed


if __name__ == "__main__":
    rpc_client = RpcClient(info.RABBITMQ_SERVER, info.RABBITMQ_USER, info.RABBITMQ_PASS, '/test1')

    print(" [x] Requesting page")
    for i in range(50):
        tic()
        response = rpc_client.call('/')
        print(response['stat'])
        toc_print()
        time.sleep(.1)
    print(" [.] Got %r" % response)
