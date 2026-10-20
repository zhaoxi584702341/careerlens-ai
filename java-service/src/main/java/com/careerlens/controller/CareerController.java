package com.careerlens.controller;

import com.careerlens.config.PythonServiceConfig;
import com.careerlens.dto.AnalyzeRequest;
import com.careerlens.dto.JobMatchRequest;
import com.careerlens.dto.RadarRequest;
import com.careerlens.exception.UpstreamErrorException;
import com.careerlens.exception.UpstreamTimeoutException;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

import java.net.SocketTimeoutException;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class CareerController {

    @Autowired
    private RestTemplate restTemplate;

    @Autowired
    private PythonServiceConfig pythonServiceConfig;

    /**
     * 简历解析 - 转发到 Python
     * BFF: POST /api/analyze-resume → 此接口: POST /api/analyze
     */
    @PostMapping("/analyze")
    public ResponseEntity<Object> analyze(@Valid @RequestBody AnalyzeRequest request) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("resume_text", request.getResumeText());
        return forward("/api/analyze", payload);
    }

    /**
     * 岗位匹配 - 转发到 Python
     * BFF: POST /api/match-job → 此接口: POST /api/match
     */
    @PostMapping("/match")
    public ResponseEntity<Object> match(@Valid @RequestBody JobMatchRequest request) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("resume_text", request.getResumeText());
        payload.put("job_description", request.getJobDescription());
        return forward("/api/match", payload);
    }

    /**
     * 简历优化 - 转发到 Python
     * BFF: POST /api/optimize-resume → 此接口: POST /api/optimize
     */
    @PostMapping("/optimize")
    public ResponseEntity<Object> optimize(@Valid @RequestBody JobMatchRequest request) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("resume_text", request.getResumeText());
        payload.put("job_description", request.getJobDescription());
        return forward("/api/optimize", payload);
    }

    /**
     * 能力雷达 - 转发到 Python
     * BFF: POST /api/radar → 此接口: POST /api/radar
     * Python 端该接口字段为 resume / jd
     */
    @PostMapping("/radar")
    public ResponseEntity<Object> radar(@Valid @RequestBody RadarRequest request) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("resume", request.getResume());
        payload.put("jd", request.getJd());
        return forward("/api/radar", payload);
    }

    /**
     * 健康检查
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "java-service"));
    }

    /**
     * 统一转发逻辑：POST 到 Python 服务对应路径，返回 Python 的原始响应体。
     * 注意：调用方需传入符合 Python 端字段命名（snake_case）的 Map。
     *
     * <p>不在此处捕获异常，而是按类型抛出，交由 {@code GlobalExceptionHandler}
     * 统一转换为 contracts/error-envelope.schema.json 定义的错误信封，
     * 以保证错误码（UPSTREAM_ERROR / UPSTREAM_TIMEOUT / SERVICE_UNAVAILABLE）
     * 与 requestId 全链路追踪生效。
     */
    @SuppressWarnings("rawtypes")
    private ResponseEntity<Object> forward(String path, Map<String, Object> payload) {
        String url = pythonServiceConfig.getPythonServiceUrl() + path;
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        long javaStarted = System.currentTimeMillis();
        try {
            ResponseEntity<Map> response = restTemplate.exchange(
                    url, HttpMethod.POST, new HttpEntity<>(payload, headers), Map.class);
            Map<String, Object> body = response.getBody();
            injectJavaTiming(body, System.currentTimeMillis() - javaStarted);
            return ResponseEntity.ok(body);
        } catch (RestClientResponseException e) {
            // 下游返回非 2xx → UPSTREAM_ERROR (502)
            throw new UpstreamErrorException(
                    "Python 服务返回 " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
        } catch (ResourceAccessException e) {
            // 连接失败或读超时：区分超时与不可达
            if (hasTimeoutCause(e)) {
                throw new UpstreamTimeoutException("Python 服务响应超时", e);
            }
            throw e; // → SERVICE_UNAVAILABLE (503)
        }
    }

    /**
     * 在 Python 返回体的 meta.timings 中补齐 java 段（Java 层端到端耗时，含等待 Python）。
     * timings 各段为嵌套包含关系，total 由 BFF 汇总，语义见 contracts/openapi.yaml。
     * 若下游未返回 meta/timings 结构则跳过，不阻断主流程。
     */
    @SuppressWarnings("unchecked")
    private void injectJavaTiming(Map<String, Object> body, long javaMs) {
        if (body == null) {
            return;
        }
        Object metaObj = body.get("meta");
        if (!(metaObj instanceof Map)) {
            return;
        }
        Object timingsObj = ((Map<String, Object>) metaObj).get("timings");
        if (timingsObj instanceof Map) {
            ((Map<String, Object>) timingsObj).put("java", javaMs);
        }
    }

    /** 判断异常链中是否存在读超时（SocketTimeoutException）。 */
    private boolean hasTimeoutCause(Throwable e) {
        Throwable current = e;
        while (current != null) {
            if (current instanceof SocketTimeoutException) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }
}
