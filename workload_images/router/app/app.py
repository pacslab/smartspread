import time

from flask import Flask, Response

from RPCClient import RpcClient, tic, toc_print

app = Flask(__name__, static_url_path='/asdhbasidhbasihdb')

import RabbitServerInfo as info

rpc_client = RpcClient(info.RABBITMQ_SERVER, info.RABBITMQ_USER, info.RABBITMQ_PASS, '/test1', timeout=10000)


import logging
logging.basicConfig(level=logging.DEBUG)
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)


@app.route('/')
@app.route('/<path:p>')
def wiki_proxy(p=''):
    if not p.startswith('/'):
        p = '/' + p

    ps = p[1:].split('/', 1)
    rpc_queue = "/" + ps[0]
    p = "/" + "/".join(ps[1:])

    print(rpc_queue)
    print(p)

    print(" [x] Requesting page")
    tic()
    
    response = rpc_client.call(p, rpc_queue=rpc_queue)

    toc_print()

    hdr = response['headers']
    for h in hdr:
        if h[0] in ['Transfer-Encoding', 'Date', 'Connection', ]:
            hdr.remove(h)

    resp = Response(response['body'], status=response['stat'], headers=hdr)
    return resp


if __name__ == '__main__':
    app.run()
