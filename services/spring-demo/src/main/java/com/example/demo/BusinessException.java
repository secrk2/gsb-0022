package com.example.demo;

/**
 * 演示用业务异常：制造带全限定类名的异常堆栈首行，
 * 供采集链路验证多行合并与 exception_class 提取。
 */
public class BusinessException extends RuntimeException {

    public BusinessException(String message) {
        super(message);
    }

    public BusinessException(String message, Throwable cause) {
        super(message, cause);
    }
}
