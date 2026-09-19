#!/bin/sh
# 持续向本机 nginx 发请求，制造混合状态码的访问日志。
# busybox wget 已随 alpine 提供，无需额外安装。

URLS_OK="/ / /index.html /health /api/users /api/orders/1024 /api/products?page=2 /static/app.js /static/logo.png /search?q=guandemo /search?q=spring"
URLS_WARN="/forbidden /static/missing.css /api/not-found"
URLS_ERR="/error"
UA_POOL="Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0|curl/8.7.0|GuanlanBot/1.0|Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/605.1.15"

pick() {
  # 从竖线/空格分隔的池子里伪随机取一个
  echo "$1" | tr '|' '\n' | awk -v seed="$RANDOM" '
    BEGIN { srand(seed) }
    { a[NR] = $0 }
    END { print a[int(rand() * NR) + 1] }'
}

i=0
while true; do
  i=$((i + 1))
  roll=$((RANDOM % 100))

  if [ "$roll" -lt 70 ]; then
    path=$(pick "$(echo "$URLS_OK" | tr ' ' '|')")
  elif [ "$roll" -lt 90 ]; then
    path=$(pick "$(echo "$URLS_WARN" | tr ' ' '|')")
  else
    path=$URLS_ERR
  fi

  # 再掺入随机不存在的路径，保证有自然 404
  if [ $((i % 7)) -eq 0 ]; then
    path="/lost/req-$i.html"
  fi

  ua=$(pick "$UA_POOL")
  if [ $((i % 3)) -eq 0 ]; then
    wget -q -O /dev/null --header="Referer: http://dashboard.guanlan.local/" -U "$ua" "http://127.0.0.1$path"
  else
    wget -q -O /dev/null -U "$ua" "http://127.0.0.1$path"
  fi

  # 约每秒 2~5 条
  sleep "0.$(printf '%d' $((200 + RANDOM % 300)))"
done
