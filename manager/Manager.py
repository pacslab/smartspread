"""
Robust Consumer that will automatically re-connect on failure.
"""
import logging
import random
import time

import numpy as np
import pandas as pd

import amqpstorm
from amqpstorm import Connection

import RabbitServerInfo as info
import DockerRemoteAPI as api
from ELSbeat import metricbeat
import LoadTester

logging.basicConfig(level=logging.INFO)

LOGGER = logging.getLogger()


class PackageInfo(object):
    def __init__(self, image_name, test_url, mem_limit, post_delay, cpu_percent_limit=None, environment=None,
                 device_read_bps=None, device_read_iops=None, device_write_bps=None, device_write_iops=None):
        if environment is None:
            environment = []
        if device_read_bps is None:
            device_read_bps = []
        if device_read_iops is None:
            device_read_iops = []
        if device_write_bps is None:
            device_write_bps = []
        if device_write_iops is None:
            device_write_iops = []

        self.image_name = image_name
        self.test_url = test_url
        self.mem_limit = mem_limit
        self.post_delay = post_delay
        self.environment = environment
        self.cpu_percent_limit = cpu_percent_limit
        self.device_read_bps = device_read_bps
        self.device_read_iops = device_read_iops
        self.device_write_bps = device_write_bps
        self.device_write_iops = device_write_iops

    def __str__(self):
        return self.image_name + ":" + self.mem_limit + " - ENV:" + str(self.environment)

    def __unicode__(self):
        return self.__str__()

    def __repr__(self):
        return self.__str__()


class RpcManager(object):
    def __init__(self, max_retries=None):
        self.max_retries = max_retries
        self.connection = None

    def create_connection(self):
        """Create a connection.
        :return:
        """
        attempts = 0
        while True:
            attempts += 1
            try:
                self.connection = Connection(info.RABBITMQ_SERVER, info.RABBITMQ_USER, info.RABBITMQ_PASS,
                                             heartbeat=info.RABBITMQ_HB)
                break
            except amqpstorm.AMQPError as why:
                LOGGER.exception(why)
                if self.max_retries and attempts > self.max_retries:
                    break
                time.sleep(min(attempts * 2, 30))
            except KeyboardInterrupt:
                break

    def start(self):
        """Start the Consumers.
        :return:
        """
        if not self.connection:
            self.create_connection()
        while True:
            try:
                channel = self.connection.channel()
                
                while True:
                    my_args = info.args
                    my_args['x-max-length'] = 100
                    my_args['x-message-ttl'] = 10000
                    ret = channel.queue.declare('/fileio', passive=True)
                    print('Messages in queue: {}'.format(ret['message_count']))
                    time.sleep(0.1)
                    
            except amqpstorm.AMQPError as why:
                LOGGER.exception(why)
                self.create_connection()
            except KeyboardInterrupt:
                self.connection.close()
                break

    def __call__(self, message):
        print("Message:", message.body)
        message.ack()


class ApiServer(object):
    def __init__(self, name, ip, api_port, id):
        self.name = name
        self.ip = ip
        self.api_port = api_port
        self.id = id

    def get_api_url(self):
        return 'http://{0}:{1}'.format(self.ip, self.api_port)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.__str__()

    def __repr__(self):
        return self.__str__()


class Manager(object):
    def __init__(self, elastic_server_ip, elastic_server_port, profiler, workers):
        self.elastic_server_ip = elastic_server_ip
        self.elastic_server_port = elastic_server_port
        self.profiler = profiler
        self.workers = workers
        self.MAX_PRE_CONTAINER_COUNT = 5
        self.MIN_PRE_CONTAINER_COUNT = 1
        self.MAX_PACKAGE_PER_WORKER = 6
        self.NORMALIZED_LATENCY_THRESHOLD = 2.5

        self.worker_package_counts = None

        self.profiler_api = api.DockerRemoteAPI(base_url=self.profiler.get_api_url())

        self.worker_apis = []
        self.last_workers_stats = []
        for worker in self.workers:
            worker_api = api.DockerRemoteAPI(base_url=worker.get_api_url())
            self.worker_apis.append(worker_api)

        self.test_load_testers = []

    def prepare_profile(self, package):
        # We should only have one instance of this container, delete all before it
        print("Deleting all containers...")
        self.profiler_api.delete_all()
        print("Creating an instance of the package...")
        
        Manager.create_package_on_worker(package, self.profiler_api)
        time.sleep(package.post_delay)
        print('Container creation done!')

    def get_random_base(self, tests_targets, test_mode='RPS'):
        test_state = []

        if len(tests_targets) == 0:
            raise Exception('Test Targets cannot have a length of zero!')

        total_count = 0
        for test_target in tests_targets:
            if test_mode == "RPS":
                rand_rps = random.choice(test_target['target_rps_list'])
                rand_count = random.choice(test_target['counts'])

                rand_test = {
                    'package': test_target['package'],
                    'rps_each': rand_rps,
                    'count': rand_count,
                }

                total_count += rand_count

                test_state.append(rand_test)
            elif test_mode == "Interactive":
                rand_users = random.choice(test_target['target_users'])
                rand_count = random.choice(test_target['counts'])

                rand_test = {
                    'package': test_target['package'],
                    'users_each': rand_users,
                    'count': rand_count,
                }

                total_count += rand_count

                test_state.append(rand_test)

        if total_count == 0:
            print('Zero for the total count!')
            return self.get_random_base(tests_targets, test_mode)

        # TODO: get this from the input for different VM sizes
        # if we put too many, we won't have enough space on the ram!
        if total_count > self.MAX_PRE_CONTAINER_COUNT:
            print('Large Total count!')
            return self.get_random_base(tests_targets, test_mode)
        if total_count < self.MIN_PRE_CONTAINER_COUNT:
            print('Too Little Total count!')
            return self.get_random_base(tests_targets, test_mode)

        return test_state

    def prepare_worker_test(self, target_profile, test_time, warmup_time, worker_num=0, test_mode='RPS'):
        package = target_profile['package']

        # Create the instance
        worker = self.workers[worker_num]
        worker_api = api.DockerRemoteAPI(base_url=worker.get_api_url())
        worker_api.create(package.image_name, mem_limit=package.mem_limit, cpu_percent_limit=package.cpu_percent_limit,
                          environment=package.environment, device_read_bps=package.device_read_bps,
                          device_read_iops=package.device_read_iops,
                          device_write_bps=package.device_write_bps, device_write_iops=package.device_write_iops)
        time.sleep(package.post_delay)

        # Start the load testing
        if test_mode == "RPS":
            load_tester = LoadTester.LoadTester(package.test_url, timeout=test_time, warmup=warmup_time)
            load_tester.perform_test_rps_async(rps=target_profile['target_rps'])
        elif test_mode == "Interactive":
            load_tester = LoadTester.LoadTester(package.test_url, timeout=test_time, warmup=warmup_time,
                                                num_of_clients=int(target_profile['num_of_clients']))
            load_tester.perform_test_async()
        else:
            raise Exception("Invalid Test Mode!!!")

        return load_tester

    def prepare_worker(self, tests_targets, worker_num=0, test_mode='RPS'):
        # We clear profiler for this task as well, so it won't respond to tasks
        self.profiler_api.delete_all()
        # We should only have one instance of this container, delete all before it
        worker = self.workers[worker_num]
        worker_api = api.DockerRemoteAPI(base_url=worker.get_api_url())

        test_states = self.get_random_base(tests_targets, test_mode)

        print("Deleting all containers...")
        worker_api.delete_all()
        print("Creating an instances of the packages...")

        all_post_delays = []
        for test_state in test_states:
            count = test_state['count']
            package = test_state['package']
            all_post_delays.append(package.post_delay)

            if count > 0:
                for i in range(count):
                    worker_api.create(package.image_name, mem_limit=package.mem_limit,
                                      cpu_percent_limit=package.cpu_percent_limit,
                                      environment=package.environment,
                                      device_read_bps=package.device_read_bps,
                                      device_read_iops=package.device_read_iops,
                                      device_write_bps=package.device_write_bps,
                                      device_write_iops=package.device_write_iops)
                    print('Container creation done: ', package)

        time.sleep(max(all_post_delays))
        time.sleep(10)

        self.test_load_testers = []
        if test_mode == "RPS":
            for test_state in test_states:
                count = test_state['count']
                package = test_state['package']
                rps_each = test_state['rps_each']
                all_post_delays.append(package.post_delay)

                if count > 0:
                    load_tester = LoadTester.LoadTester(package.test_url, timeout='24h', warmup='30s')
                    load_tester.perform_test_rps_async(rps=rps_each * count)
                    self.test_load_testers.append(load_tester)
        elif test_mode == "Interactive":
            for test_state in test_states:
                count = test_state['count']
                package = test_state['package']
                users_each = test_state['users_each']
                all_post_delays.append(package.post_delay)

                if count > 0:
                    load_tester = LoadTester.LoadTester(package.test_url, timeout='24h', warmup='30s',
                                                num_of_clients=users_each * count)
                    load_tester.perform_test_async()
                    self.test_load_testers.append(load_tester)

        return test_states

    def stop_test_load(self):
        for load_tester in self.test_load_testers:
            load_tester.stop_test()

        for idx, load_tester in enumerate(self.test_load_testers):
            print('-------------')
            print(load_tester.url)
            load_tester.wait_for_test_results()
            load_tester.print_results()

        print('All load testers have been stopped!')

    def profile(self, package, warmup_time, test_time, target_rps, accepted_stats, count=10, test_mode='RPS'):
        all_results = None
        for i in range(count):
            print("starting test #", i + 1)
            profile_results = self.profile_once(package, warmup_time, test_time, target_rps, accepted_stats, test_mode)
            if all_results is None:
                all_results = profile_results
            else:
                for key in profile_results:
                    all_results[key].append(profile_results[key][0])

            # let is get back to the original state
            time.sleep(30)

        return all_results

    def profile_once(self, package, warmup_time, test_time, target_rps, accepted_stats, test_mode='RPS'):
        warmup_time_secs = LoadTester.convert_to_seconds(warmup_time)
        test_time_secs = LoadTester.convert_to_seconds(test_time)
        metric_start_time = 'now-' + test_time

        metricbeatinstance = metricbeat(self.elastic_server_ip, self.elastic_server_port, self.profiler.id)

        def get_statistics():
            return metricbeatinstance.GetStatistics(start_time=metric_start_time,
                                                    duration_in_seconds=test_time_secs)

        empty_stats = {}
        stats = get_statistics()
        for key in stats:
            for key2 in stats[key]:
                if key2 in accepted_stats:
                    empty_stats[key + "-" + key2] = []

        empty_results = {}
        for key in LoadTester.LoadTester.result_keys:
            empty_results[key] = []

        total_stats = empty_stats
        total_results = empty_results

        if test_mode == 'RPS':
            load_tester = LoadTester.LoadTester(package.test_url, timeout=test_time, warmup=warmup_time)
            load_tester.perform_test_rps_async(rps=target_rps)
        elif test_mode == 'Interactive':
            load_tester = LoadTester.LoadTester(package.test_url, timeout=test_time, warmup=warmup_time,
                                                num_of_clients=target_rps)
            load_tester.perform_test_async()

        else:
            raise Exception("Invalid Test Mode!!!")

        time.sleep(test_time_secs + warmup_time_secs - 1)

        stats = get_statistics()
        for key in stats:
            for key2 in stats[key]:
                if key2 in accepted_stats:
                    total_stats[key + "-" + key2].append(stats[key][key2])

        print('Wating for load tester results...')
        load_tester.wait_for_test_results()
        test_results = load_tester.results()
        for key in test_results:
            total_results[key].append(test_results[key])

        total_results.update(total_stats)
        return total_results

    def get_worker_stats(self, test_time, accepted_stats=None, worker_num=0):
        if accepted_stats is None:
            accepted_stats = ['avg']

        total_stats = {}
        stats = self.get_worker_statistics(test_time, worker_num)
        for key in stats:
            for key2 in stats[key]:
                if key2 in accepted_stats:
                    total_stats[key + "-" + key2] = stats[key][key2]

        return total_stats

    def get_worker_statistics(self, test_time, worker_num=0):
        worker = self.workers[worker_num]
        metric_start_time = 'now-' + test_time
        test_time_secs = LoadTester.convert_to_seconds(test_time)

        metricbeatinstance = metricbeat(self.elastic_server_ip, self.elastic_server_port,
                                        worker.id)

        return metricbeatinstance.GetStatistics(start_time=metric_start_time,
                                                duration_in_seconds=test_time_secs)

    def get_worker_api(self, worker_num):
        return self.worker_apis[worker_num]

    def clear_all_workers(self):
        for i in range(len(self.workers)):
            worker_api = self.get_worker_api(i)
            worker_api.delete_all()

    def prepare_workers_for_experiment(self, packages, package_selection_method='random', MAX_PACKAGE_PER_WORKER=None,
                                       NORMALIZED_LATENCY_THRESHOLD=None, test_time='1m'):
        if MAX_PACKAGE_PER_WORKER is not None:
            self.MAX_PACKAGE_PER_WORKER = MAX_PACKAGE_PER_WORKER
        if NORMALIZED_LATENCY_THRESHOLD is not None:
            self.NORMALIZED_LATENCY_THRESHOLD = NORMALIZED_LATENCY_THRESHOLD

        self.clear_all_workers()
        self.update_worker_stats(test_time)

        worker_package_counts = []
        for worker in self.workers:
            worker_package_count = {}
            for package in packages:
                worker_package_count[package.image_name] = 0
            worker_package_counts.append(worker_package_count)
        self.worker_package_counts = worker_package_counts

        for package in packages:
            self.add_package(package, package_selection_method)

    @staticmethod
    def create_package_on_worker(package, worker_api):
        worker_api.create(package.image_name, mem_limit=package.mem_limit,
                          cpu_percent_limit=package.cpu_percent_limit, environment=package.environment,
                          device_read_bps=package.device_read_bps, device_read_iops=package.device_read_iops,
                          device_write_bps=package.device_write_bps, device_write_iops=package.device_write_iops)

    def update_worker_stats(self, test_time):
        self.last_workers_stats = []
        for idx, worker in enumerate(self.workers):
            stats = self.get_worker_stats(test_time, worker_num=idx)
            self.last_workers_stats.append(stats)

    def perform_experiment(self, packages, package_sequences, package_max_latencies, sequence_len,
                           test_time='1m', warmup_time='10s',
                           package_selection_method='random'):
        test_time_secs = LoadTester.convert_to_seconds(test_time)
        warmup_time_secs = LoadTester.convert_to_seconds(warmup_time)

        # For initial status
        self.update_worker_stats(test_time)

        results = []
        for time_step in range(sequence_len):
            print('++++++++++++++++++++++++++')
            print('time step #', time_step)

            valid_test = False
            first_time = True
            test_results = {}
            result = {}
            package_load_testers = []

            retry_count = 0
            ITERATION_REPEAT_LIMIT = 3
            while not valid_test:
                result = {
                    'time': time_step,
                }

                package_load_testers = []
                for idx, package in enumerate(packages):
                    load_tester = LoadTester.LoadTester(package.test_url, timeout=test_time, warmup=warmup_time,
                                                        num_of_clients=package_sequences[idx][time_step])
                    load_tester.perform_test_async()
                    package_load_testers.append(load_tester)

                time.sleep(test_time_secs + warmup_time_secs - 1)

                # Gather the worker stats
                self.update_worker_stats(test_time)

                total_valid_test = True
                for idx, load_tester in enumerate(package_load_testers):
                    load_tester.stop_test()
                    load_tester.prepare_results()
                    test_results = load_tester.results()
                    print(load_tester.url)
                    load_tester.print_results()

                    if test_results['avg_ms'] < package_max_latencies[idx] and test_results['completed'] > 20:
                        valid_test = True
                    else:
                        available_worker_nums, total_counts = self.get_available_workers()
                        if len(available_worker_nums) > 0:
                            self.add_package(packages[idx], package_selection_method=package_selection_method)
                            valid_test = False
                        else:
                            valid_test = True
                    if not valid_test:
                        total_valid_test=False

                    for key in test_results:
                        result[packages[idx].image_name + "-" + key] = test_results[key]
                        
                valid_test = total_valid_test

                first_time = False

                for load_tester in package_load_testers:
                    test_results = load_tester.results()
                    if test_results['avg_ms'] == 0 or test_results['completed'] < 20:
                        print('Bad Average or Too little completed tasks!')
                        valid_test = False
                        first_time = True

                for idx, package in enumerate(packages):
                    package_count = 0
                    for worker_num, worker in enumerate(self.workers):
                        package_count += self.worker_package_counts[worker_num][package.image_name]
                    result[package.image_name + "-count"] = package_count

                    result[package.image_name + "-user_count"] = package_sequences[idx][time_step]

                retry_count += 1
                # Let it end in the end, even if we don't get to where we want!
                if retry_count > (ITERATION_REPEAT_LIMIT - 1):
                    print('This iteration never converged!!!')
                    valid_test = True

            if retry_count > (ITERATION_REPEAT_LIMIT - 1):
                print('This iteration never converged!!!')
            else:
                for load_tester in package_load_testers:
                    test_results = load_tester.results()
                    if test_results['avg_ms'] == 0 or test_results['completed'] < 20:
                        raise Exception("Zero latency reported! something went wrong!")
            print(result)
            results.append(result)

        return results

    def add_package(self, package, package_selection_method='random'):
        worker_num = self.select_worker_for_package(package=package, method=package_selection_method)
        print('selected_worker: ', worker_num)
        if worker_num < 0:
            print('cannot add a new container!')
            return worker_num

        print('worker # ', worker_num, ' status: ')
        print(self.worker_package_counts[worker_num])

        # Add the package
        Manager.create_package_on_worker(package, self.get_worker_api(worker_num=worker_num))
        time.sleep(package.post_delay)

        print('package successfully added!')
        self.worker_package_counts[worker_num][package.image_name] += 1
        print('worker # ', worker_num, ' status: ')
        print(self.worker_package_counts[worker_num])
        return worker_num
    
    def get_available_workers(self):
        available_worker_nums = []
        total_counts = []
        for idx, worker_package_count in enumerate(self.worker_package_counts):
            total_count = 0
            for key in worker_package_count:
                total_count += worker_package_count[key]
            if total_count < self.MAX_PACKAGE_PER_WORKER:
                available_worker_nums.append(idx)
                total_counts.append(total_count)
                
        return available_worker_nums, total_counts

    def select_worker_for_package(self, package, method='random'):
        available_worker_nums, total_counts = self.get_available_workers()
        
        count_sums = 0
        for total_count in total_counts:
            count_sums += total_count

        print("available workers: ", available_worker_nums)

        if len(available_worker_nums) == 0:
            return -1

        if method == 'random':
            return random.choice(available_worker_nums)
        # Here we fill them one by one, since we only add, it is the same as binpack
        # TODO: later we should check them out, but now we only increase capacity
        elif method == 'binpack':
            if 1 in available_worker_nums:
                if 'file' in package.image_name:
                    return 1
            if 2 in available_worker_nums:
                if 'oltp' in package.image_name:
                    return 2
            return available_worker_nums[0]
        # Find one that has the lowest containers in it
        elif method == 'dispatch':
            min_idx = -1
            min_count = 100
            for idx, worker_num in enumerate(available_worker_nums):
                if total_counts[idx] < min_count:
                    min_count = total_counts[idx]
                    min_idx = idx

            return available_worker_nums[min_idx]
        elif method == 'ml':
            from sklearn.externals import joblib
            from keras.models import load_model
            test_mode = 'Interactive'

            users_target = 1

            model_file_name = 'Models/nn_tp.h5'
            scaler_file_name_x = 'Models/scaler_x.joblib'
            scaler_file_name_y = 'Models/scaler_y.joblib'
            predictor_columns = ['cpu_idle-avg_pre', 'cpu_idle-avg_profile', 'cpu_io_wait-avg_pre',
                                 'cpu_io_wait-avg_profile', 'cpu_usr-avg_pre', 'cpu_usr-avg_profile',
                                 'dsreads-avg_pre', 'dsreads-avg_profile', 'dswrites-avg_pre',
                                 'dswrites-avg_profile', 'mem_used_pct-avg_pre',
                                 'mem_used_pct-avg_profile', 'nbr-avg_pre', 'nbr-avg_profile', 'nbs-avg_pre',
                                 'nbs-avg_profile',
                                 'readtime-avg_pre', 'readtime-avg_profile', 'writetime-avg_pre',
                                 'writetime-avg_profile', ]

            regressor = load_model(model_file_name)
            sc_X = joblib.load(scaler_file_name_x)
            sc_y = joblib.load(scaler_file_name_y)

            def get_distance(x):
                if x['package_name'] == package.image_name:
                    return np.abs(x['num_of_clients'] - users_target)
                else:
                    return 10000

            profiles = pd.read_csv('ProfileTable_' + test_mode + '.csv')
            profiles.set_index('Unnamed: 0', inplace=True)

            dist = profiles.apply(get_distance, axis=1)
            profile_id = dist.idxmin()

            profile_row = profiles.iloc[profile_id, :]
            profile_dict = profile_row.to_dict()

            # In the beginning (only one container for each workload), we want spread
            if count_sums < 3:
                return self.select_worker_for_package(package, method='dispatch')
            
            predicted_tps_normalized = []
            for idx, worker_num in enumerate(available_worker_nums):
                worker_stat = self.last_workers_stats[worker_num]
                all_dict = {}
                for key in worker_stat:
                    all_dict[key + '_pre'] = worker_stat[key]
                for key in profile_dict:
                    all_dict[key + '_profile'] = profile_dict[key]

                dataset = pd.DataFrame(data=all_dict, index=[0])
                
                timer = LoadTester.TimerClass()
                timer.tic()
                
                X = dataset[predictor_columns]
                X = sc_X.transform(X)
                y_pred = regressor.predict(X).flatten()
                y_pred = sc_y.inverse_transform(y_pred)
                y_pred = y_pred[0]
                predicted_tps_normalized.append(y_pred)
                
                print(timer.toc() * 1000)

            print("Throughput Predictions: ", predicted_tps_normalized)
            max_idx = -1
            max_tp = -100
            for idx, worker_num in enumerate(available_worker_nums):
                if predicted_tps_normalized[idx] > max_tp:
                    max_tp = predicted_tps_normalized[idx]
                    max_idx = idx

            if max_idx == -1:
                return -1
            else:
                return available_worker_nums[max_idx]


# Extra stuff removed into Jupyter notebook file
if __name__ == '__main__':
    manager = RpcManager()
    manager.start()
