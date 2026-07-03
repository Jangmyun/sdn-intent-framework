#!/bin/bash

docker rm -f onos 2>/dev/null

docker run -d \
  --name onos \
  --network host \
  onosproject/onos:2.7-latest

sleep 15

docker exec -it onos /root/onos/bin/onos-app localhost activate org.onosproject.openflow
docker exec -it onos /root/onos/bin/onos-app localhost activate org.onosproject.fwd

sudo ss -lntp | grep 6653
