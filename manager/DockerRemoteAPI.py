# import the standard JSON parser
import json
import time

import requests


class DockerError(Exception):
    pass


class ContainerNotFoundError(DockerError):
    pass


class ContainerCreationError(DockerError):
    pass


class InvalidStatusError(Exception):
    pass


class InvalidContentError(Exception):
    pass


class Container(object):
    def __init__(self, short_id, d=None, base_url='http://10.12.7.28:7999'):
        self.short_id = short_id
        self.base_url = base_url
        self.stat = None

        if d is not None:
            self.id = d['short_id']
            self.mem_max_usage = d['mem_max_usage']
            self.mem_limit = d['mem_limit']
            self.name = d['name']
            self.cpu_percent = d['cpu_percent']
            self.status = d['status']
            self.mem_usage = d['mem_usage']
            self.image_tags = d['image_tags']
        else:
            self.id = None
            self.mem_max_usage = None
            self.mem_limit = None
            self.name = None
            self.cpu_percent = None
            self.status = None
            self.mem_usage = None
            self.image_tags = None

    def __str__(self):
        return self.short_id

    def __unicode__(self):
        return self.__str__()

    def __repr__(self):
        return self.__str__()

    def get_stat(self):
        resp = requests.get(self.base_url + "/container/" + self.short_id, params={}, timeout=20)
        status = resp.status_code
        if status == 200 or status == 201:
            try:
                rbody = json.loads(resp.content)
            except:
                print(rbody)
                raise InvalidContentError('Cannot Decode JSON')

            if self.short_id in rbody:
                stat = rbody[self.short_id]
                self.stat = stat
                self._update_stat()
                return stat
            else:
                print(rbody)
                raise ContainerNotFoundError('Container specified doesn\'t exist!')
        else:
            raise InvalidStatusError('Get Status Failed')

    def delete(self):
        resp = requests.delete(self.base_url + "/container/" + self.short_id, params={})
        status = resp.status_code
        if status == 200 or status == 201:
            try:
                rbody = json.loads(resp.content)
            except Exception:
                raise InvalidContentError('Cannot Decode JSON')

            if rbody['status_code'] == 200:
                return
            else:
                print(rbody)
                raise ContainerNotFoundError('Container specified doesn\'t exist!')
        else:
            raise InvalidStatusError('Get Status Failed')

    def _update_stat(self):
        attrs = ['id', 'mem_max_usage', 'mem_limit', 'name', 'cpu_percent', 'status', 'mem_usage']
        for attr in attrs:
            setattr(self, attr, self.stat[attr])

    def print_stats(self):
        if self.stat is None:
            self.get_stat()

        self.print_properties()

    def print_properties(self):
        attrs = ['id', 'mem_max_usage', 'mem_limit', 'name', 'cpu_percent', 'status', 'mem_usage', 'short_id']
        print("------------------------------------------------------")
        for attr in attrs:
            x = getattr(self, attr)
            print('%15s' % attr, ": ", x)
        print("------------------------------------------------------")


class DockerRemoteAPI(object):
    def __init__(self, base_url='http://10.12.7.28:7999'):
        self.base_url = base_url

    # the rest library can't distinguish between a property and a list of properties with one element.
    # this function converts a json object into a list with many, one, or no elements
    # o is the dictionary containing the list
    # key is the key containing the list (if any)
    def container_to_list(self, o):
        if isinstance(o, dict):
            elements = []
            for key in o:
                obj = o[key]
                obj['short_id'] = key
                container = Container(key, obj, base_url=self.base_url)
                elements.append(container)
            return elements
        else:
            return []

    def list(self):
        resp = requests.get(self.base_url + "/container", params={}, timeout=20)

        status = resp.status_code
        if status == 200:
            rbody = json.loads(resp.content)
            containers = self.container_to_list(rbody)
            return containers
        else:
            return []

    def delete_all(self):
        containers = self.list()
        for container in containers:
            container.delete()

    def create(self, image_name, mem_limit=None, cpu_percent_limit=None, ports=None, environment=None,
               device_read_bps=None, device_read_iops=None,
               device_write_bps=None, device_write_iops=None
               ):
        params = {
            'image_name': image_name
        }
        if mem_limit is not None:
            params['mem_limit'] = mem_limit
        if cpu_percent_limit is not None:
            params['cpu_percent_limit'] = cpu_percent_limit
        if ports is not None:
            params['ports'] = ports
        if environment is not None:
            params['environment'] = environment
        if device_read_bps is not None:
            if len(device_read_bps) > 0:
                params['device_read_bps'] = device_read_bps
        if device_read_iops is not None:
            if len(device_read_iops) > 0:
                params['device_read_iops'] = device_read_iops
        if device_write_bps is not None:
            if len(device_write_bps) > 0:
                params['device_write_bps'] = device_write_bps
        if device_write_iops is not None:
            if len(device_write_iops) > 0:
                params['device_write_iops'] = device_write_iops

        print(params)

        resp = requests.post(self.base_url + "/container", json=params, timeout=20)

        status = resp.status_code
        if status == 200:
            try:
                rbody = json.loads(resp.content)
            except Exception:
                raise InvalidContentError('Cannot Decode JSON')

            if rbody['status_code'] == 201:
                return rbody['target']
            else:
                print(params)
                print(rbody)
                raise ContainerCreationError('The status for container creation failed!')
        else:
            raise InvalidStatusError('status returned is not acceptable')


if __name__ == '__main__':
    docker_remote = DockerRemoteAPI(base_url='http://10.2.6.177:7999')
    containers = docker_remote.list()
    print(containers)

    # if len(containers) > 0:
    #     print(containers[0])
    #     # containers[0].print_properties()
    #     # time.sleep(5)
    #     # containers[0].get_stat()
    #     # containers[0].print_stats()
    # else:
    #     print("There are no containers in this system!")

    # for container in containers:
    #     container.delete()

    short_id = docker_remote.create('YOUR_HUB_ID/fileio-automated', mem_limit="256m")
    short_id = docker_remote.create('YOUR_HUB_ID/linpack-automated', mem_limit="256m")
    short_id = docker_remote.create('YOUR_HUB_ID/oltp-automated', mem_limit="256m")
    # print(short_id)
    # container = Container(short_id)
    # container.get_stat()
    # container.print_stats()

    containers = docker_remote.list()
    print(containers)

    # container.delete()
    #
    # containers = docker_remote.list()
    # print(containers)
