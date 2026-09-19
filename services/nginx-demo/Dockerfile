FROM nginx:1.27-alpine

# tzdata：让 access.log 的 $time_local 带服务所在时区（+0800）
RUN apk add --no-cache tzdata

# 官方镜像把 access.log 做成了指向 /dev/stdout 的软链，卷初始化时会被原样复制进卷，
# 导致 nginx 只往 stdout 写、卷里从无真实文件，Filebeat 采集不到。这里删掉让它落成真文件。
RUN rm -f /var/log/nginx/access.log /var/log/nginx/error.log

ENV TZ=Asia/Shanghai

COPY nginx.conf /etc/nginx/nginx.conf
COPY traffic.sh /traffic.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /traffic.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
