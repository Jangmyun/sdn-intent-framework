#!/bin/bash

sudo mn -c

sudo mn \
  --topo single,3 \
  --controller remote,ip=127.0.0.1,port=6653 \
  --switch ovsk,protocols=OpenFlow13
