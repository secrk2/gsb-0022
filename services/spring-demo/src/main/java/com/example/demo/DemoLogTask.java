package com.example.demo;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 持续产生应用日志：常规 DEBUG/INFO/WARN，周期性抛出带多行堆栈
 * （含 Caused by 链）的异常，供 Filebeat multiline 验证。
 */
@Component
public class DemoLogTask {

    private static final Logger log = LoggerFactory.getLogger(DemoLogTask.class);

    private final AtomicLong seq = new AtomicLong();

    private static final List<String> USERS = Arrays.asList(
            "alice", "bob", "carol", "dave", "erin");
    private static final List<String> ORDER_EVENTS = Arrays.asList(
            "order.created", "order.paid", "order.shipped",
            "order.cancelled", "order.refunded");

    @Scheduled(fixedDelay = 1000, initialDelay = 3000)
    public void heartbeat() {
        long n = seq.incrementAndGet();
        if (n % 5 == 0) {
            log.debug("调度心跳第 {} 次，JVM 空闲内存 {} MB",
                    n, Runtime.getRuntime().freeMemory() / 1024 / 1024);
        } else {
            String user = USERS.get((int) (n % USERS.size()));
            log.info("处理用户请求成功 user={} event={} traceId=tr-{}-{}",
                    user, ORDER_EVENTS.get((int) (n % ORDER_EVENTS.size())), n, n * 31L);
        }
    }

    @Scheduled(fixedDelay = 3500, initialDelay = 8000)
    public void businessFlow() {
        long n = seq.get();
        if (n % 4 == 0) {
            log.warn("下游支付渠道响应偏慢 cost={}ms channel=wechat-pay orderId={}",
                    1200 + (n % 900), 10000 + n);
        } else {
            log.info("库存校验通过 sku=SKU-{} warehouse=hz-01 qty={}",
                    1000 + (n % 50), 1 + (n % 20));
        }
    }

    /** 每 ~18 秒抛一次异常，堆栈经 logback 原样多行写入 application.log。 */
    @Scheduled(fixedDelay = 18000, initialDelay = 12000)
    public void failureSimulation() {
        long n = seq.incrementAndGet();
        String type = Map.of(
                0, "db", 1, "remote", 2, "validation").get((int) (n % 3));
        try {
            switch (type) {
                case "db" -> queryDatabase(n);
                case "remote" -> callRemote(n);
                default -> validate(n);
            }
        } catch (Exception ex) {
            log.error("业务处理失败 orderId={} stage={}", 10000 + n, type, ex);
        }
    }

    private void queryDatabase(long n) {
        try {
            throw new java.sql.SQLException("Connection refused (Connection timed out)");
        } catch (java.sql.SQLException e) {
            throw new BusinessException("查询订单库失败 orderId=" + (10000 + n), e);
        }
    }

    private void callRemote(long n) {
        try {
            throw new java.io.IOException("HTTP 503 Service Unavailable from inventory-service");
        } catch (java.io.IOException e) {
            throw new BusinessException("调用库存服务超时 sku=SKU-" + (1000 + n % 50), e);
        }
    }

    private void validate(long n) {
        throw new IllegalArgumentException("订单金额不能为负数 amount=-" + (n % 50));
    }
}
