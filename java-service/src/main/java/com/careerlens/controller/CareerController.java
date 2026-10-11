package com.careerlens.controller;

import com.careerlens.config.PythonServiceConfig;
import com.careerlens.dto.AnalyzeRequest;
import com.careerlens.dto.JobMatchRequest;
import com.careerlens.dto.RadarRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
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
    public ResponseEntity<Object> analyze(@RequestBody AnalyzeRequest request) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("resume_text", request.getResumeText());
        return forward("/api/analyze", payload);
    }

    /**
     * 岗位匹配 - 转发到 Python
     * BFF: POST /api/match-job → 此接口: POST /api/match
     */
    @PostMapping("/match")
    public ResponseEntity<Object> match(@RequestBody JobMatchRequest request) {
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
    public ResponseEntity<Object> optimize(@RequestBody JobMatchRequest request) {
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
    public ResponseEntity<Object> radar(@RequestBody RadarRequest request) {
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
     * 异常时返回 500 与友好提示。
     */
    @SuppressWarnings("rawtypes")
    private ResponseEntity<Object> forward(String path, Map<String, Object> payload) {
        String url = pythonServiceConfig.getPythonServiceUrl() + path;
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            ResponseEntity<Map> response = restTemplate.exchange(
                    url, HttpMethod.POST, new HttpEntity<>(payload, headers), Map.class);
            return ResponseEntity.ok(response.getBody());
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of(
                    "error", "Python服务调用失败: " + e.getMessage()
            ));
        }
    }
}
