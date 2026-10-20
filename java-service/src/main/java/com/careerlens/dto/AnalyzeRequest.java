package com.careerlens.dto;

import jakarta.validation.constraints.NotBlank;

public class AnalyzeRequest {
    @NotBlank(message = "resumeText 不能为空")
    private String resumeText;

    public AnalyzeRequest() {}

    public AnalyzeRequest(String resumeText) {
        this.resumeText = resumeText;
    }

    public String getResumeText() { return resumeText; }
    public void setResumeText(String resumeText) { this.resumeText = resumeText; }
}
