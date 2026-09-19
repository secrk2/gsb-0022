#!/bin/sh
set -e

mkdir -p /var/log/nginx

# 前台启动 nginx（daemon off），后台跑流量生成器
nginx
echo "nginx 已启动，开始产生访问流量 ..."
exec /traffic.sh
