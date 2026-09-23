#!/bin/bash
pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple ray 2>&1 | tail -1
export VLLM_HOST_IP=10.100.168.1
exec ray start --address=10.100.168.2:6379 --node-ip-address 10.100.168.1 --block --disable-usage-stats
