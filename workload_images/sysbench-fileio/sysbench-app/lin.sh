#!/usr/bin/env sh
 sysbench --test=fileio --file-total-size=100M --file-test-mode=rndrw --max-time=0 --max-requests=200 run
