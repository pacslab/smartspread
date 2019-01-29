RABBITMQ_SERVER = 'RABBITMQ_SERVER'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'admin'
RABBITMQ_PASS = 'RABBITMQ_PASS'
RABBITMQ_HB = 10

QUEUE_TIMEOUT = 5000  # in ms
QUEUE_MAX_LEN = 1000  # maximum jobs that can be queued

args = {
    'x-max-length': QUEUE_MAX_LEN,  # maximum length of queue, will receive nack afterwards
    'x-overflow': 'reject-publish',  # Reject the new publish with a nack
    'x-message-ttl': QUEUE_TIMEOUT,
}


def add_arguments(parser):
    '''
    Adds necessary arguments to the parser
    '''
    parser.add_argument('-w', '--website', type=str, nargs='?',
                        help='The url that this RPC server will be serving. eg. http://127.0.0.1:80',
                        default='http://127.0.0.1:80')
    parser.add_argument('-q', '--queue', type=str, nargs='?',
                        help='The main task queue name that will be used.', default='/test1')
    parser.add_argument('-s', '--rmq-server', type=str, nargs='?',
                        help='The rabbitmq server we will connect to.', default=RABBITMQ_SERVER)
    parser.add_argument('-u', '--rmq-user', type=str, nargs='?',
                        help='The username of rabbitmq server we will connect to.', default=RABBITMQ_USER)
    parser.add_argument('-p', '--rmq-pass', type=str, nargs='?',
                        help='The username of rabbitmq server we will connect to.', default=RABBITMQ_PASS)
    parser.add_argument('-b', '--heartbeat', type=str, nargs='?',
                        help='The username of rabbitmq server we will connect to.', default=RABBITMQ_HB)
    parser.add_argument('-m', '--max-length', type=int, nargs='?',
                        help='The maximum length of the queue that will be declared.',
                        default=args['x-max-length'])
    parser.add_argument('-t', '--message-ttl', type=int, nargs='?',
                        help='The time-to-live based in ms.',
                        default=args['x-message-ttl'])
