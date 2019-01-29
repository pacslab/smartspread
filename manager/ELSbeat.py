from elasticsearch import Elasticsearch
import numpy as np
import time


class metricbeat:
    def __init__(self, ELSaddress, ELSport, worker_node_hostname):
        self.hostname = worker_node_hostname
        self.es = Elasticsearch([{"host": ELSaddress, "port": ELSport}])
        self.system_modules = ["cpu", "diskio", "network", "process_summary","memory"]
        self.stats = {"avg": 0, "min": 0, "max": 0, "std": 0, "percentile5": 0, "percentile95": 0}
        self.statistics_list = ["cpu_time", "cpu_usr", "cpu_krn", "cpu_idle", "cpu_io_wait", "cpu_sint_time", "dsr",
                                "dsreads", "drm", "readtime", "dsw", "dswrites", "dwm", "writetime", "nbr", "nbs",
                                "loadavg","mem_used_bytes","mem_used_pct"]

    def QuerySysteMmodule(self, start_time="now-1m", duration_in_seconds=0, wait=False):
        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"host.name": self.hostname}},
                        {"match": {"metricset.module": "system"}},
                        {"match": {"metricset.name": "cpu"}}
                    ],
                    "filter": [
                        {"range": {"@timestamp": {"gte": start_time}}}
                    ]
                }
            },
            "sort": [
                {"@timestamp": "asc"}
            ]
        }
        res_dict = {}
        if (wait == True):
            time.sleep(duration_in_seconds)
        for item in self.system_modules:
            query_body["query"]["bool"]["must"][2]["match"]["metricset.name"] = item
            res_dict[item] = self.es.search(doc_type="doc", body=query_body, size=60)["hits"]
        return res_dict

    def GetStatistics(self, start_time="now-1m", duration_in_seconds=0, wait=False):
        dic = {}
        module_total = {}
        for item in self.statistics_list:
            dic[item] = {"avg": 0, "min": 0, "max": 0, "std": 0, "percentile5": 0, "percentile95": 0}
        try:
            res_dict = self.QuerySysteMmodule(start_time, duration_in_seconds, wait)
            for item in self.system_modules:
                if (res_dict[item]["total"] == 0):
                    return dic
                else:
                    module_total[item] = res_dict[item]["total"]
        except:
            return dic
        cpu_time_series = []
        cpu_usr_series = []
        cpu_krn_series = []
        cpu_idle_series = []
        cpu_io_wait_series = []
        cpu_sint_time_series = []
        for i in range(module_total["cpu"]):
            cpu_usr_series.append(res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["user"]["ticks"])
            cpu_krn_series.append(res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["system"]["ticks"])
            cpu_idle_series.append(res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["idle"]["ticks"])
            cpu_io_wait_series.append(res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["iowait"]["ticks"])
            cpu_sint_time_series.append(res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["softirq"]["ticks"])
            cpu_time_series.append(cpu_usr_series[i] + cpu_krn_series[i] + cpu_idle_series[i] + cpu_io_wait_series[i] +
                                   cpu_sint_time_series[i] +
                                   res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["nice"]["ticks"] +
                                   res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["irq"]["ticks"] +
                                   res_dict["cpu"]["hits"][i]["_source"]["system"]["cpu"]["steal"]["ticks"])
        dsr_series = []
        dsreads_series = []
        drm_series = []
        readtime_series = []
        dsw_series = []
        dswrites_series = []
        dwm_series = []
        writetime_series = []
        for i in range(module_total["diskio"]):
            dsr_series.append(res_dict["diskio"]["hits"][i]['_source']['system']["diskio"]["read"]["bytes"] / 512.0)
            dsreads_series.append(res_dict["diskio"]["hits"][i]['_source']['system']["diskio"]["read"]["count"])
            drm_series.append(res_dict["diskio"]["hits"][i]["_source"]["system"]["diskio"]["iostat"]["read"]["request"][
                                  "merges_per_sec"])
            readtime_series.append(res_dict["diskio"]["hits"][i]['_source']['system']["diskio"]["read"]["time"])
            dsw_series.append(res_dict["diskio"]["hits"][i]['_source']['system']["diskio"]["write"]["bytes"] / 512.0)
            dswrites_series.append(res_dict["diskio"]["hits"][i]['_source']['system']["diskio"]["write"]["count"])
            dwm_series.append(
                res_dict["diskio"]["hits"][i]["_source"]["system"]["diskio"]["iostat"]["write"]["request"][
                    "merges_per_sec"])
            writetime_series.append(res_dict["diskio"]["hits"][i]['_source']['system']["diskio"]["write"]["time"])
        nbr_series = []
        nbs_series = []
        for i in range(module_total["network"]):
            nbr_series.append(res_dict["network"]["hits"][i]['_source']['system']["network"]["out"]["bytes"])
            nbs_series.append(res_dict["network"]["hits"][i]['_source']['system']["network"]["in"]["bytes"])
        loadavg_series = []
        for i in range(module_total["process_summary"]):
            loadavg_series.append(
                res_dict["process_summary"]["hits"][i]['_source']['system']['process']['summary']['running'])
        mem_used_bytes_series = []
        mem_used_pct_series = []
        for i in range(module_total["memory"]):
            mem_used_bytes_series.append(
                res_dict["memory"]["hits"][i]['_source']['system']['memory']['actual']['used']['bytes'])
            mem_used_pct_series.append(
                res_dict["memory"]["hits"][i]['_source']['system']['memory']['actual']['used']['pct'])
        cpu_time_series = [y - x for x, y in zip(cpu_time_series, cpu_time_series[1:])]
        cpu_usr_series = [y - x for x, y in zip(cpu_usr_series, cpu_usr_series[1:])]
        cpu_krn_series = [y - x for x, y in zip(cpu_krn_series, cpu_krn_series[1:])]
        cpu_idle_series = [y - x for x, y in zip(cpu_idle_series, cpu_idle_series[1:])]
        cpu_io_wait_series = [y - x for x, y in zip(cpu_io_wait_series, cpu_io_wait_series[1:])]
        cpu_sint_time_series = [y - x for x, y in zip(cpu_io_wait_series, cpu_sint_time_series[1:])]
        dsr_series = [y - x for x, y in zip(dsr_series, dsr_series[1:])]
        dsreads_series = [y - x for x, y in zip(dsreads_series, dsreads_series[1:])]
        readtime_series = [y - x for x, y in zip(readtime_series, readtime_series[1:])]
        dsw_series = [y - x for x, y in zip(dsw_series, dsw_series[1:])]
        dswrites_series = [y - x for x, y in zip(dswrites_series, dswrites_series[1:])]
        writetime_series = [y - x for x, y in zip(writetime_series, writetime_series[1:])]
        nbr_series = [y - x for x, y in zip(nbr_series, nbr_series[1:])]
        nbs_series = [y - x for x, y in zip(nbs_series, nbs_series[1:])]
        dic["cpu_time"]["avg"] = np.mean(cpu_time_series)
        dic["cpu_time"]["min"] = np.min(cpu_time_series)
        dic["cpu_time"]["max"] = np.max(cpu_time_series)
        dic["cpu_time"]["std"] = np.std(cpu_time_series)
        dic["cpu_time"]["percentile5"] = np.percentile(cpu_time_series, 5)
        dic["cpu_time"]["percentile95"] = np.percentile(cpu_time_series, 95)
        dic["cpu_usr"]["avg"] = np.mean(cpu_usr_series)
        dic["cpu_usr"]["min"] = np.min(cpu_usr_series)
        dic["cpu_usr"]["max"] = np.max(cpu_usr_series)
        dic["cpu_usr"]["std"] = np.std(cpu_usr_series)
        dic["cpu_usr"]["percentile5"] = np.percentile(cpu_usr_series, 5)
        dic["cpu_usr"]["percentile95"] = np.percentile(cpu_usr_series, 95)
        dic["cpu_krn"]["avg"] = np.mean(cpu_krn_series)
        dic["cpu_krn"]["min"] = np.min(cpu_krn_series)
        dic["cpu_krn"]["max"] = np.max(cpu_krn_series)
        dic["cpu_krn"]["std"] = np.std(cpu_krn_series)
        dic["cpu_krn"]["percentile5"] = np.percentile(cpu_krn_series, 5)
        dic["cpu_krn"]["percentile95"] = np.percentile(cpu_krn_series, 95)
        dic["cpu_idle"]["avg"] = np.mean(cpu_idle_series)
        dic["cpu_idle"]["min"] = np.min(cpu_idle_series)
        dic["cpu_idle"]["max"] = np.max(cpu_idle_series)
        dic["cpu_idle"]["std"] = np.std(cpu_idle_series)
        dic["cpu_idle"]["percentile5"] = np.percentile(cpu_idle_series, 5)
        dic["cpu_idle"]["percentile95"] = np.percentile(cpu_idle_series, 95)
        dic["cpu_io_wait"]["avg"] = np.mean(cpu_io_wait_series)
        dic["cpu_io_wait"]["min"] = np.min(cpu_io_wait_series)
        dic["cpu_io_wait"]["max"] = np.max(cpu_io_wait_series)
        dic["cpu_io_wait"]["std"] = np.std(cpu_io_wait_series)
        dic["cpu_io_wait"]["percentile5"] = np.percentile(cpu_io_wait_series, 5)
        dic["cpu_io_wait"]["percentile95"] = np.percentile(cpu_io_wait_series, 95)
        dic["cpu_sint_time"]["avg"] = np.mean(cpu_sint_time_series)
        dic["cpu_sint_time"]["min"] = np.min(cpu_sint_time_series)
        dic["cpu_sint_time"]["max"] = np.max(cpu_sint_time_series)
        dic["cpu_sint_time"]["std"] = np.std(cpu_sint_time_series)
        dic["cpu_sint_time"]["percentile5"] = np.percentile(cpu_sint_time_series, 5)
        dic["cpu_sint_time"]["percentile95"] = np.percentile(cpu_sint_time_series, 95)
        dic["dsr"]["avg"] = np.mean(dsr_series)
        dic["dsr"]["min"] = np.min(dsr_series)
        dic["dsr"]["max"] = np.max(dsr_series)
        dic["dsr"]["std"] = np.std(dsr_series)
        dic["dsr"]["percentile5"] = np.percentile(dsr_series, 5)
        dic["dsr"]["percentile95"] = np.percentile(dsr_series, 95)
        dic["dsreads"]["avg"] = np.mean(dsreads_series)
        dic["dsreads"]["min"] = np.min(dsreads_series)
        dic["dsreads"]["max"] = np.max(dsreads_series)
        dic["dsreads"]["std"] = np.std(dsreads_series)
        dic["dsreads"]["percentile5"] = np.percentile(dsreads_series, 5)
        dic["dsreads"]["percentile95"] = np.percentile(dsreads_series, 95)
        dic["drm"]["avg"] = np.mean(drm_series)
        dic["drm"]["min"] = np.min(drm_series)
        dic["drm"]["max"] = np.max(drm_series)
        dic["drm"]["std"] = np.std(drm_series)
        dic["drm"]["percentile5"] = np.percentile(drm_series, 5)
        dic["drm"]["percentile95"] = np.percentile(drm_series, 95)
        dic["readtime"]["avg"] = np.mean(readtime_series)
        dic["readtime"]["min"] = np.min(readtime_series)
        dic["readtime"]["max"] = np.max(readtime_series)
        dic["readtime"]["std"] = np.std(readtime_series)
        dic["readtime"]["percentile5"] = np.percentile(readtime_series, 5)
        dic["readtime"]["percentile95"] = np.percentile(readtime_series, 95)
        dic["dsw"]["avg"] = np.mean(dsw_series)
        dic["dsw"]["min"] = np.min(dsw_series)
        dic["dsw"]["max"] = np.max(dsw_series)
        dic["dsw"]["std"] = np.std(dsw_series)
        dic["dsw"]["percentile5"] = np.percentile(dsw_series, 5)
        dic["dsw"]["percentile95"] = np.percentile(dsw_series, 95)
        dic["dswrites"]["avg"] = np.mean(dswrites_series)
        dic["dswrites"]["min"] = np.min(dswrites_series)
        dic["dswrites"]["max"] = np.max(dswrites_series)
        dic["dswrites"]["std"] = np.std(dswrites_series)
        dic["dswrites"]["percentile5"] = np.percentile(dswrites_series, 5)
        dic["dswrites"]["percentile95"] = np.percentile(dswrites_series, 95)
        dic["dwm"]["avg"] = np.mean(dwm_series)
        dic["dwm"]["min"] = np.min(dwm_series)
        dic["dwm"]["max"] = np.max(dwm_series)
        dic["dwm"]["std"] = np.std(dwm_series)
        dic["dwm"]["percentile5"] = np.percentile(dwm_series, 5)
        dic["dwm"]["percentile95"] = np.percentile(dwm_series, 95)
        dic["writetime"]["avg"] = np.mean(writetime_series)
        dic["writetime"]["min"] = np.min(writetime_series)
        dic["writetime"]["max"] = np.max(writetime_series)
        dic["writetime"]["std"] = np.std(writetime_series)
        dic["writetime"]["percentile5"] = np.percentile(writetime_series, 5)
        dic["writetime"]["percentile95"] = np.percentile(writetime_series, 95)
        dic["nbr"]["avg"] = np.mean(nbr_series)
        dic["nbr"]["min"] = np.min(nbr_series)
        dic["nbr"]["max"] = np.max(nbr_series)
        dic["nbr"]["std"] = np.std(nbr_series)
        dic["nbr"]["percentile5"] = np.percentile(nbr_series, 5)
        dic["nbr"]["percentile95"] = np.percentile(nbr_series, 95)
        dic["nbs"]["avg"] = np.mean(nbs_series)
        dic["nbs"]["min"] = np.min(nbs_series)
        dic["nbs"]["max"] = np.max(nbs_series)
        dic["nbs"]["std"] = np.std(nbs_series)
        dic["nbs"]["percentile5"] = np.percentile(nbs_series, 5)
        dic["nbs"]["percentile95"] = np.percentile(nbs_series, 95)
        dic["loadavg"]["avg"] = np.mean(loadavg_series)
        dic["loadavg"]["min"] = np.min(loadavg_series)
        dic["loadavg"]["max"] = np.max(loadavg_series)
        dic["loadavg"]["std"] = np.std(loadavg_series)
        dic["loadavg"]["percentile5"] = np.percentile(loadavg_series, 5)
        dic["loadavg"]["percentile95"] = np.percentile(loadavg_series, 95)
        dic["mem_used_bytes"]["avg"] = np.mean(mem_used_bytes_series)
        dic["mem_used_bytes"]["min"] = np.min(mem_used_bytes_series)
        dic["mem_used_bytes"]["max"] = np.max(mem_used_bytes_series)
        dic["mem_used_bytes"]["std"] = np.std(mem_used_bytes_series)
        dic["mem_used_bytes"]["percentile5"] = np.percentile(mem_used_bytes_series, 5)
        dic["mem_used_bytes"]["percentile95"] = np.percentile(mem_used_bytes_series, 95)
        dic["mem_used_pct"]["avg"] = np.mean(mem_used_pct_series)
        dic["mem_used_pct"]["min"] = np.min(mem_used_pct_series)
        dic["mem_used_pct"]["max"] = np.max(mem_used_pct_series)
        dic["mem_used_pct"]["std"] = np.std(mem_used_pct_series)
        dic["mem_used_pct"]["percentile5"] = np.percentile(mem_used_pct_series, 5)
        dic["mem_used_pct"]["percentile95"] = np.percentile(mem_used_pct_series, 95)
        return dic