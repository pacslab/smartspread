#!/usr/bin/env sh
 sysbench --max-time=10 --max-requests=2500 --test=cpu --cpu-max-prime=1000 run
