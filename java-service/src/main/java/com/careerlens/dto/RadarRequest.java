package com.careerlens.dto;

import jakarta.validation.constraints.NotBlank;

public class RadarRequest {
    @NotBlank(message = "resume 不能为空")
    private String resume;
    @NotBlank(message = "jd 不能为空")
    private String jd;

    public RadarRequest() {}

    public RadarRequest(String resume, String jd) {
        this.resume = resume;
        this.jd = jd;
    }

    public String getResume() { return resume; }
    public void setResume(String resume) { this.resume = resume; }
    public String getJd() { return jd; }
    public void setJd(String jd) { this.jd = jd; }
}
