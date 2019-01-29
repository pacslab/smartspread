#!/bin/sh
curl -L -O https://artifacts.elastic.co/downloads/beats/metricbeat/metricbeat-6.4.1-amd64.deb                                                                             
sudo dpkg -i metricbeat-6.4.1-amd64.deb
cd ../yml/
sudo sed -i "90i\ \ index: \"${HOSTNAME}-metricbeat-%{[beat.version]}-%{+yyyy.MM.dd}\"" metricbeat.yml
sudo sed -i "23isetup.template.name: \"${HOSTNAME}\"" metricbeat.yml
sudo sed -i "23isetup.template.pattern: \"${HOSTNAME}-*\"" metricbeat.yml
sudo sed -i "23isetup.dashboards.index: \"${HOSTNAME}-*\"" metricbeat.yml
sudo rm -rf /etc/metricbeat/metricbeat.yml
sudo rm -rf /etc/metricbeat/modules.d/system.yml
sudo rm -rf /etc/metricbeat/modules.d/docker.yml.disabled
sudo cp ./metricbeat.yml /etc/metricbeat/metricbeat.yml
sudo cp ./system.yml /etc/metricbeat/modules.d/system.yml
sudo cp ./docker.yml /etc/metricbeat/modules.d/docker.yml
sudo service metricbeat start