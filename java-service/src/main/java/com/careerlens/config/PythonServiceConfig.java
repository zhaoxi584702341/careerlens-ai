package com.careerlens.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.web.client.RestTemplate;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

@Configuration
public class PythonServiceConfig {

    @Value("${python.service.url}")
    private String pythonServiceUrl;

    /**
     * RestTemplate 使用 application.yml 中配置的 http.client 超时时间
     * （connect-timeout 10s / read-timeout 120s），保证 LLM 长链路调用不提前中断。
     *
     * 关键修复：RestTemplate 默认的 StringHttpMessageConverter（索引 1）使用 ISO-8859-1，
     * 会导致 Python 服务返回的 UTF-8 中文被错误解码为乱码/问号。
     * Spring 匹配消息转换器按列表顺序遍历，若以追加方式注册 UTF-8 转换器，
     * 靠前的 ISO-8859-1 转换器会优先命中，乱码依旧存在。
     * 因此这里直接覆盖索引 1 处的默认转换器，将其替换为 UTF-8 版本。
     */
    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        RestTemplate restTemplate = builder
                .setConnectTimeout(Duration.ofSeconds(10))
                .setReadTimeout(Duration.ofSeconds(120))
                .build();

        // 替换索引 1 处的 StringHttpMessageConverter 为 UTF-8 版本
        restTemplate.getMessageConverters().set(1,
                new StringHttpMessageConverter(StandardCharsets.UTF_8));

        return restTemplate;
    }

    public String getPythonServiceUrl() {
        return pythonServiceUrl;
    }
}
