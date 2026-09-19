package com.example.demo;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 让演示服务成为一个真正在跑 HTTP 的 Spring Boot 应用。 */
@RestController
public class DemoController {

    @GetMapping("/")
    public Map<String, Object> index() {
        return Map.of("app", "guanlan-spring-demo", "status", "running");
    }

    @GetMapping("/api/orders")
    public Map<String, Object> orders(@RequestParam(defaultValue = "20") int size) {
        return Map.of("size", size, "warehouse", "hz-01");
    }
}
