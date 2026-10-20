package com.careerlens.dto;

import jakarta.validation.constraints.NotBlank;

public class JobMatchRequest {
    @NotBlank(message = "resumeText 不能为空")
    private String resumeText;
    @NotBlank(message = "jobDescription 不能为空")
    private String jobDescription;

    public JobMatchRequest() {}

    public JobMatchRequest(String resumeText, String jobDescription) {
        this.resumeText = resumeText;
        this.jobDescription = jobDescription;
    }

    public String getResumeText() { return resumeText; }
    public void setResumeText(String resumeText) { this.resumeText = resumeText; }
    public String getJobDescription() { return jobDescription; }
    public void setJobDescription(String jobDescription) { this.jobDescription = jobDescription; }
}
