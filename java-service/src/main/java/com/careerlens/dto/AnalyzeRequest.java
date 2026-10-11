package com.careerlens.dto;

public class AnalyzeRequest {
    private String resumeText;

    public AnalyzeRequest() {}

    public AnalyzeRequest(String resumeText) {
        this.resumeText = resumeText;
    }

    public String getResumeText() { return resumeText; }
    public void setResumeText(String resumeText) { this.resumeText = resumeText; }
}
