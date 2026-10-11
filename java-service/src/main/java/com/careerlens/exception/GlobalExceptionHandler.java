package com.careerlens.exception;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.ResourceAccessException;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 全局异常处理器：将所有异常统一转换为 contracts/error-envelope.schema.json 定义的结构。
 *
 * <p>错误信封结构：
 * <pre>
 * {
 *   "requestId": "...",
 *   "success": false,
 *   "error": { "code": "...", "message": "...", "degraded": false }
 * }
 * </pre>
 *
 * <p>错误码映射（见 contracts/error-codes.md）：
 * <ul>
 *   <li>入参校验失败 → VALIDATION_ERROR (400)</li>
 *   <li>下游读超时 → UPSTREAM_TIMEOUT (504)</li>
 *   <li>下游返回 5xx → UPSTREAM_ERROR (502)</li>
 *   <li>下游连接失败 → SERVICE_UNAVAILABLE (503)</li>
 *   <li>未归类异常 → INTERNAL_ERROR (500)</li>
 * </ul>
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** JSR-380 校验失败：@Valid 触发 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Object> handleValidation(MethodArgumentNotValidException e,
                                                   HttpServletRequest request) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(FieldError::getDefaultMessage)
                .orElse("请求参数错误");
        return envelope(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message, request);
    }

    /** 请求体缺失 / JSON 非法 */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Object> handleUnreadable(HttpMessageNotReadableException e,
                                                    HttpServletRequest request) {
        return envelope(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求体格式错误或缺失", request);
    }

    /** 下游读超时 */
    @ExceptionHandler(UpstreamTimeoutException.class)
    public ResponseEntity<Object> handleUpstreamTimeout(UpstreamTimeoutException e,
                                                        HttpServletRequest request) {
        log.warn("下游服务超时: {}", e.getMessage());
        return envelope(HttpStatus.GATEWAY_TIMEOUT, "UPSTREAM_TIMEOUT",
                "下游服务响应超时，请稍后重试", request);
    }

    /** 下游返回非 2xx */
    @ExceptionHandler(UpstreamErrorException.class)
    public ResponseEntity<Object> handleUpstreamError(UpstreamErrorException e,
                                                      HttpServletRequest request) {
        log.error("下游服务错误: {}", e.getMessage());
        return envelope(HttpStatus.BAD_GATEWAY, "UPSTREAM_ERROR",
                "下游服务返回异常，请稍后重试", request);
    }

    /** 下游连接失败（不可达） */
    @ExceptionHandler(ResourceAccessException.class)
    public ResponseEntity<Object> handleServiceUnavailable(ResourceAccessException e,
                                                           HttpServletRequest request) {
        log.error("下游服务不可达: {}", e.getMessage());
        return envelope(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                "下游服务不可用，请检查 Python 服务是否已启动", request);
    }

    /** 兜底：未归类的服务端异常 */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Object> handleInternal(Exception e, HttpServletRequest request) {
        log.error("服务内部异常", e);
        return envelope(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR",
                "服务内部错误，请稍后重试", request);
    }

    /**
     * 构造统一错误信封。requestId 优先取上游透传的 X-Request-Id，缺失时本地生成，
     * 并回写到响应头，保证全链路可追踪。
     */
    private ResponseEntity<Object> envelope(HttpStatus status, String code, String message,
                                            HttpServletRequest request) {
        String requestId = request.getHeader("X-Request-Id");
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }

        Map<String, Object> error = new LinkedHashMap<>();
        error.put("code", code);
        error.put("message", message);
        error.put("degraded", false);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("requestId", requestId);
        body.put("success", false);
        body.put("error", error);

        return ResponseEntity.status(status)
                .header("X-Request-Id", requestId)
                .body(body);
    }
}
