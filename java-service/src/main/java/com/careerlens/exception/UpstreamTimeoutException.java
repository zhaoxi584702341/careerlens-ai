package com.careerlens.exception;

/**
 * 下游 Python 服务响应超时（读超时）。
 * 由全局异常处理器映射为 UPSTREAM_TIMEOUT (504)。
 */
public class UpstreamTimeoutException extends RuntimeException {
    public UpstreamTimeoutException(String message, Throwable cause) {
        super(message, cause);
    }
}
