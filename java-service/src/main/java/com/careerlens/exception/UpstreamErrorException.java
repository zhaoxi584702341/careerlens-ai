package com.careerlens.exception;

/**
 * 下游 Python 服务返回非 2xx 响应。
 * 由全局异常处理器映射为 UPSTREAM_ERROR (502)。
 */
public class UpstreamErrorException extends RuntimeException {
    public UpstreamErrorException(String message, Throwable cause) {
        super(message, cause);
    }
}
