import platform
import time
import os

from flask import Flask, jsonify

app = Flask(__name__)
import subprocess

class TimerClass:
    def __init__(self):
        self.start_time = time.time()

    def tic(self):
        self.start_time = time.time()

    def toc(self):
        elapsed = time.time() - self.start_time
        return elapsed

    def toc_print(self):
        elapsed = time.time() - self.start_time
        print('{:4.02f}'.format(elapsed))
        return elapsed


timer = TimerClass()

@app.route('/')
def hello_world():
    timer.tic()
    if platform.platform().startswith('Windows'):
        subproc = subprocess.run(["linpack_xeon64.exe", "i1"], shell=True, stdout=subprocess.PIPE)
    else:
        subproc = subprocess.run(["/code/lin.sh"], shell=True, stdout=subprocess.PIPE)
    elapsed = timer.toc()

    if platform.platform().startswith('Windows'):
        res_args = subproc.stdout.decode('unicode_escape').split('\r\n')
    else:
        res_args = subproc.stdout.decode('unicode_escape').split('\n')

    result = {
        'output': res_args,
        'runtime': elapsed,
        'hostname': os.environ['hostname'],
        'postfix': os.environ['postfix'],
    }

    return jsonify(result)


if __name__ == '__main__':
    app.run()
