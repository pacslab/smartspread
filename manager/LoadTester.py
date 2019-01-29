import http.client
import socket
import threading
import time

from urllib.parse import urlparse
import numpy as np


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


class ClientThread(threading.Thread):
    def __init__(self, url, latencies, fails, completed, single=False, **kwargs):
        super(ClientThread, self).__init__()
        self.url = url
        # if daemon is true this thread will die when the main thread dies
        self.daemon = True
        self.done = False
        self.timer = TimerClass()
        self.total_timer = TimerClass()
        self.latencies = latencies
        self.fails = fails
        self.completed = completed
        self.timeout = kwargs.pop('timeout', 10)
        self.sock_timeout = kwargs.pop('sock_timeout', 10)
        self.warmup = kwargs.pop('warmup', 1)
        self.o = urlparse(self.url)
        self.host = self.o.netloc
        self.path = self.o.path
        self.single = single

        self.stop_signal = False

        if self.o.scheme == 'https':
            self.conn = http.client.HTTPSConnection(self.host, timeout=self.sock_timeout)
        else:
            self.conn = http.client.HTTPConnection(self.host, timeout=self.sock_timeout)

    def stop_client(self):
        self.stop_signal = True

    def run(self):
        if self.single:
            self.timer.tic()

            try:
                self.conn.request("GET", self.path)
                r = self.conn.getresponse()
                elapsed = self.timer.toc() * 1000
                body = r.read()
            except TimeoutError:
                self.fails.append(time.time())
                self.done = True
                return
            except socket.timeout:
                self.fails.append(time.time())
                self.done = True
                return
            except http.client.RemoteDisconnected:
                self.fails.append(time.time())
                self.done = True
                return
            except ConnectionResetError:
                self.done = True
                return

            if r.status == 200:
                self.completed.append(len(body))
                self.latencies.append(elapsed)
            elif r.status == 301:
                raise Exception('Got Forward page 301 status!')
            else:
                self.fails.append(time.time())
                print(r.status)

            self.done = True
            return
        else:
            self.total_timer.tic()
            while self.total_timer.toc() < self.warmup and not self.stop_signal:
                try:
                    self.conn.request("GET", self.path)
                    r = self.conn.getresponse()
                    elapsed = self.timer.toc() * 1000
                    body = r.read()
                except TimeoutError:
                    self.fails.append(time.time())
                    continue
                except socket.timeout:
                    self.fails.append(time.time())
                    continue
                except http.client.RemoteDisconnected:
                    self.fails.append(time.time())
                    continue
                except ConnectionResetError:
                    continue
                except http.client.CannotSendRequest:
                    time.sleep(.1)
                    if self.o.scheme == 'https':
                        self.conn = http.client.HTTPSConnection(self.host, timeout=self.sock_timeout)
                    else:
                        self.conn = http.client.HTTPConnection(self.host, timeout=self.sock_timeout)
                    continue

                if r.status == 200:
                    continue
                elif r.status == 301:
                    raise Exception('Got Forward page 301 status!')
                else:
                    print(r.status)

            self.total_timer.tic()
            if self.timeout > 0:
                while self.total_timer.toc() < self.timeout and not self.stop_signal:
                    self.timer.tic()

                    try:
                        self.conn.request("GET", self.path)
                        r = self.conn.getresponse()
                        elapsed = self.timer.toc() * 1000
                        body = r.read()
                    except TimeoutError:
                        self.fails.append(time.time())
                        continue
                    except socket.timeout:
                        self.fails.append(time.time())
                        continue
                    except http.client.RemoteDisconnected:
                        self.fails.append(time.time())
                        continue
                    except ConnectionResetError:
                        continue
                    except http.client.CannotSendRequest:
                        time.sleep(.1)
                        if self.o.scheme == 'https':
                            self.conn = http.client.HTTPSConnection(self.host, timeout=self.sock_timeout)
                        else:
                            self.conn = http.client.HTTPConnection(self.host, timeout=self.sock_timeout)
                        continue

                    if r.status == 200:
                        self.completed.append(len(body))
                        self.latencies.append(elapsed)
                    elif r.status == 301:
                        raise Exception('Got Forward page 301 status!')
                    else:
                        self.fails.append(time.time())
                        print(r.status)
            self.done = True


seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def convert_to_seconds(s):
    return int(s[:-1]) * seconds_per_unit[s[-1]]


class LoadTester:
    def __init__(self, url, *args, **kwargs):
        self.timeout = kwargs.pop('timeout', '10s')
        self.warmup = kwargs.pop('warmup', '1s')
        self.num_of_clients = kwargs.pop('num_of_clients', 10)
        self.url = url
        self.start_time = 0
        self.active_clients = []
        self.latencies = []
        self.fails = []
        self.completed = []

        self.ls = [0]
        self.total_completed = 0
        self.rps = 0
        self.total_mb = 0
        self.elapsed = 0
        self.rps_setpoint = 0.5
        self.done = False
        self.rps_mode = False
        self.stop_signal = False

    def wait_for_active_clients(self, warmup=False):
        while True:
            time.sleep(0.05)
            if not self.rps_mode:
                if len(self.active_clients) == 0:
                    return
            # If in RPS mode
            else:
                if self.done or warmup:
                    if len(self.active_clients) == 0:
                        return

            for idx, client in enumerate(self.active_clients):
                if client.done:
                    # print(idx)
                    del self.active_clients[idx]
                    # print(len(active_clients))

    def tic(self):
        self.start_time = time.time()

    def toc(self):
        return time.time() - self.start_time

    def toc_print(self):
        elapsed = time.time() - self.start_time
        print('{:4.02f}'.format(elapsed))
        return elapsed

    def perform_test(self):
        self.perform_test_async()

        self.wait_for_test_results()

    def perform_test_rps_async(self, rps=0.5):
        self.rps_mode = True
        self.done = False
        self.rps_setpoint = rps
        t1 = threading.Thread(target=self.perform_test_rps, daemon=True)
        t1.start()

    def perform_test_rps(self):
        self.rps_mode = True
        self.done = False
        time_in_secs = convert_to_seconds(self.timeout)
        warmup_in_secs = convert_to_seconds(self.warmup)

        timer = TimerClass()

        # perform warmup
        print("warming up...")
        self.tic()
        
        while self.toc() < warmup_in_secs and not self.stop_signal:
            timer.tic()
            client = ClientThread(self.url, [], [], [], single=True)
            client.start()
            self.active_clients.append(client)

            wait_time = (1 / self.rps_setpoint) - timer.toc()
            if wait_time > 0:
                time.sleep(wait_time)

        # Perform the test
        print("starting the test...")

        self.tic()
        while self.toc() < time_in_secs and not self.stop_signal:
            timer.tic()

            client = ClientThread(self.url, self.latencies, self.fails, self.completed, single=True)
            client.start()
            self.active_clients.append(client)

            wait_time = (1 / self.rps_setpoint) - timer.toc()
            if wait_time > 0:
                time.sleep(wait_time)
        self.done = True
        self.rps_mode = False

    def stop_test(self):
        self.stop_signal = True
        for client in self.active_clients:
            client.stop_client()

    def perform_test_async(self):
        time_in_secs = convert_to_seconds(self.timeout)
        warmup_in_secs = convert_to_seconds(self.warmup)

        self.tic()
        for i in range(self.num_of_clients):
            client = ClientThread(self.url, self.latencies, self.fails, self.completed,
                                  timeout=time_in_secs, warmup=warmup_in_secs)
            client.start()
            self.active_clients.append(client)

    def wait_for_test_results(self, warmup=False):
        self.wait_for_active_clients(warmup)
        self.prepare_results()

    def prepare_results(self):
        warmup_in_secs = convert_to_seconds(self.warmup)
        self.elapsed = self.toc() - warmup_in_secs
        self.ls = np.array(self.latencies)
        self.total_completed = len(self.completed)
        self.rps = self.total_completed / self.elapsed
        self.total_mb = np.sum(self.completed) * 1.0 / 1024.0 / 1024.0

    def print_results(self):
        print("Failed: ", len(self.fails), 'Num of Clients: ', self.num_of_clients)
        print("Completed: {0}, Elapsed: {2:4.2f}, RPS: {1:4.02f}".format(self.total_completed, self.rps, self.elapsed))
        print("Total MB Rec: {0:4.02f}, Transfer Rate: {1:4.02f} MB/s".format(self.total_mb,
                                                                              self.total_mb / self.elapsed))
        if len(self.ls) == 0:
            self.ls = [0]
        print('Avg: {0:4.02f} ms, min: {1:4.02f} ms, max: {2:4.02f} ms'.format(np.average(self.ls), np.min(self.ls),
                                                                               np.max(self.ls)))

    result_keys = ['failed', 'completed', 'rps', 'elapsed', 'total_mb', 'avg_ms', 'min_ms', 'max_ms']

    def get_latencies(self):
        return self.ls

    def results(self):
        if len(self.ls) == 0:
            self.ls = [0]
        ret = {
            'failed': len(self.fails),
            'completed': self.total_completed,
            'rps': self.rps,
            'elapsed': self.elapsed,
            'total_mb': self.total_mb,
            'avg_ms': np.average(self.ls),
            'min_ms': np.min(self.ls),
            'max_ms': np.max(self.ls),
        }
        return ret


if __name__ == '__main__':
    # tester = LoadTester('https://google.com/', timeout='3s', num_of_clients=1)
    # tester.perform_test()
    # tester.print_results()

    # tester = LoadTester('http://10.2.6.171/linpack', timeout='10s', warmup='0s', num_of_clients=4)
    tester = LoadTester('http://10.2.6.171/fileio', timeout='1m', num_of_clients=10)
    # tester = LoadTester('http://10.2.6.171/oltp', timeout='10s', num_of_clients=5)
    tester.perform_test_async()

    # time.sleep(10)
    # tester.stop_test()
    # tester.prepare_results()

    tester.wait_for_test_results()

    tester.print_results()
    print(tester.results())
    tester.wait_for_test_results()
