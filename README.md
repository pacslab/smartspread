# seams2019-smartspread
Smart spread algorithm is a VM selection algorithm that is used to deploy new container in serverless computing platforms. 
## Folder content
* deploy
  * deploy.sh
  * worker.sh
* flask_api/flask -- A Flask-based REST API for collecting information about containers on nodes. ([Documentation](https://github.com/DDSystemLab/seams2019-smartspread/wiki/Docker-Flask-API))
* manager
  * DataCollector.ipynb
  * DockerRemoteAPI.py
  * ELSbeat.py -- A Python class for fetching metrics from Elasticsearch and calculating statistics. ([Documentation](https://github.com/DDSystemLab/seams2019-smartspread/wiki/Fetch-metrics-from-Elasticsearch-and-calculate-statistics))
  * ExperimentProcessing.ipynb
  * Experimenter.ipynb
  * ExperimenterAll.ipynb
  * LoadTester.py
  * Manager.py
  * ProfileTable_Interactive.csv
  * Profiler.ipynb
  * RabbitServerInfo.py
  * log.sh
  * rofile.sh
* scripts
  * api.sh -- Script to deploy Flask-based REST API on each VM.
  * metricbeat.sh  -- Script to deploy Metricbeat on each VM.
* workload_images
  * router
  * sysbench-cpu
  * sysbench-fileio
  * sysbench-oltp
* yml
  * docker.yml -- Docker module configuration file for Metricbeat
  * metricbeat.yml -- Metricbeat configuration file
  * system.yml -- System module configuration file for Metricbeat
## Prerequesites
## Usage
## Configurations
  * Operating system -- Ubuntu 18.04
  * Python 3.7
  * Metricbeat 6.4.1
