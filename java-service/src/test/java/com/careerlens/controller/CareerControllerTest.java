package com.careerlens.controller;

import com.careerlens.config.PythonServiceConfig;
import com.careerlens.exception.GlobalExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestTemplate;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * CareerController 接口测试（MockMvc 独立搭建 + MockRestServiceServer 拦截 RestTemplate）。
 *
 * <p>设计说明：Java 服务自身不含业务逻辑，唯一职责是将 BFF 的请求转换为 Python
 * 端的 snake_case 字段并转发。因此本测试聚焦两点：
 * <ol>
 *   <li>字段映射与转发路径正确（BFF 驼峰字段 → Python 下划线字段）；</li>
 *   <li>成功时透传下游响应，异常时由 GlobalExceptionHandler 按 contracts/error-envelope.schema.json 映射错误信封。</li>
 * </ol>
 * Java 服务测试无需依赖真实 Python 服务。</p>
 *
 * <p>关于模拟方式：使用 Spring 官方 {@link MockRestServiceServer} 绑定到真实 RestTemplate，
 * 无需 Mockito 对框架类做字节码增强（避免高版本 JDK 下 Could not modify all classes 报错），
 * 也不会真正发起网络请求，确保测试可独立、离线、确定性地运行。</p>
 *
 * <p>运行方式：{@code mvn -q test} 或 {@code mvn -q test -Dtest=CareerControllerTest}</p>
 */
class CareerControllerTest {

    private MockMvc mockMvc;
    private MockRestServiceServer server;

    private static final String PYTHON_URL = "http://localhost:8000";

    @BeforeEach
    void setUp() {
        // 使用真实 RestTemplate，由 MockRestServiceServer 接管其底层请求工厂
        RestTemplate restTemplate = new RestTemplate();
        server = MockRestServiceServer.bindTo(restTemplate).build();

        PythonServiceConfig config = new PythonServiceConfig();
        ReflectionTestUtils.setField(config, "pythonServiceUrl", PYTHON_URL);

        CareerController controller = new CareerController();
        ReflectionTestUtils.setField(controller, "restTemplate", restTemplate);
        ReflectionTestUtils.setField(controller, "pythonServiceConfig", config);

        // 注册全局异常处理器，使抛出的下游异常按 contracts/error-envelope.schema.json 映射为错误信封
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    // ==================== GET /api/health ====================

    @Test
    @DisplayName("健康检查：返回 UP 与 java-service")
    void health_returnsUp() throws Exception {
        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"))
                .andExpect(jsonPath("$.service").value("java-service"));
    }

    // ==================== POST /api/analyze ====================

    @Test
    @DisplayName("analyze 正常：resumeText 映射为 resume_text 并透传结果")
    void analyze_normal_forwardsSnakeCase() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/analyze"))
                .andExpect(method(HttpMethod.POST))
                // 关键断言：BFF 驼峰字段 resumeText 被转换为 Python 端 snake_case 字段 resume_text
                .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers
                        .jsonPath("$.resume_text").value("5年Java开发，熟悉MySQL"))
                .andRespond(withSuccess(
                        "{\"keywords\":[\"Java\",\"MySQL\"],\"score\":72}",
                        MediaType.APPLICATION_JSON));

        mockMvc.perform(post("/api/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeText\":\"5年Java开发，熟悉MySQL\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.keywords[0]").value("Java"))
                .andExpect(jsonPath("$.score").value(72));

        server.verify();
    }

    @Test
    @DisplayName("analyze 异常：下游 5xx 映射为 502 错误信封 UPSTREAM_ERROR")
    void analyze_downstreamFailure_returnsEnvelope() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/analyze"))
                .andRespond(withServerError());

        mockMvc.perform(post("/api/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeText\":\"简历\"}"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.requestId").exists())
                .andExpect(jsonPath("$.error.code").value("UPSTREAM_ERROR"))
                .andExpect(jsonPath("$.error.degraded").value(false));

        server.verify();
    }

    // ==================== POST /api/match ====================

    @Test
    @DisplayName("match 正常：resumeText/jobDescription 映射为 snake_case 并透传")
    void match_normal_forwardsSnakeCase() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/match"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers
                        .jsonPath("$.resume_text").value("3年前端"))
                .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers
                        .jsonPath("$.job_description").value("要求React"))
                .andRespond(withSuccess(
                        "{\"match_score\":65,\"matched_skills\":[\"Vue\"],\"missing_skills\":[\"React\"]}",
                        MediaType.APPLICATION_JSON));

        mockMvc.perform(post("/api/match")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeText\":\"3年前端\",\"jobDescription\":\"要求React\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.match_score").value(65))
                .andExpect(jsonPath("$.missing_skills[0]").value("React"));

        server.verify();
    }

    @Test
    @DisplayName("match 异常：下游 5xx 映射为 502 错误信封")
    void match_downstreamFailure_returnsEnvelope() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/match"))
                .andRespond(withServerError());

        mockMvc.perform(post("/api/match")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeText\":\"简历\",\"jobDescription\":\"岗位\"}"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("UPSTREAM_ERROR"));

        server.verify();
    }

    // ==================== POST /api/optimize ====================

    @Test
    @DisplayName("optimize 正常：透传 summary/suggestions/missing_keywords")
    void optimize_normal() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/optimize"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess(
                        "{\"summary\":\"技术栈错位\",\"suggestions\":[\"补充React经验\"],\"missing_keywords\":[\"React\"]}",
                        MediaType.APPLICATION_JSON));

        mockMvc.perform(post("/api/optimize")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeText\":\"3年前端\",\"jobDescription\":\"要求React\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.summary").value("技术栈错位"))
                .andExpect(jsonPath("$.suggestions[0]").value("补充React经验"));

        server.verify();
    }

    @Test
    @DisplayName("optimize 异常：下游 5xx 映射为 502 错误信封")
    void optimize_downstreamFailure_returnsEnvelope() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/optimize"))
                .andRespond(withServerError());

        mockMvc.perform(post("/api/optimize")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeText\":\"简历\",\"jobDescription\":\"岗位\"}"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("UPSTREAM_ERROR"));

        server.verify();
    }

    // ==================== POST /api/radar ====================

    @Test
    @DisplayName("radar 正常：字段 resume/jd 原样转发并透传 dimensions")
    void radar_normal() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/radar"))
                .andExpect(method(HttpMethod.POST))
                // radar 契约使用 resume/jd 字段（与前端、Python 保持一致）
                .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers
                        .jsonPath("$.resume").value("3年前端"))
                .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers
                        .jsonPath("$.jd").value("要求React"))
                .andRespond(withSuccess(
                        "{\"dimensions\":[{\"name\":\"技术匹配度\",\"score\":65},{\"name\":\"项目经验\",\"score\":60}]}",
                        MediaType.APPLICATION_JSON));

        mockMvc.perform(post("/api/radar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resume\":\"3年前端\",\"jd\":\"要求React\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.dimensions.length()").value(2))
                .andExpect(jsonPath("$.dimensions[0].name").value("技术匹配度"));

        server.verify();
    }

    @Test
    @DisplayName("radar 异常：下游 5xx 映射为 502 错误信封")
    void radar_downstreamFailure_returnsEnvelope() throws Exception {
        server.expect(requestTo(PYTHON_URL + "/api/radar"))
                .andRespond(withServerError());

        mockMvc.perform(post("/api/radar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resume\":\"简历\",\"jd\":\"岗位\"}"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("UPSTREAM_ERROR"));

        server.verify();
    }

    // ==================== 边界场景 ====================

    @Test
    @DisplayName("analyze 边界：空对象触发 JSR-380 校验，返回 400 校验错误信封")
    void analyze_emptyBody_returnsValidationError() throws Exception {
        // @Valid + @NotBlank 生效后，空 resumeText 由 Java 层直接拒绝，不再转发到 Python
        mockMvc.perform(post("/api/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
    }
}
