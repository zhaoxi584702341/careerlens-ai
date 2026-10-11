package com.careerlens.dto;

public class RadarRequest {
    private String resume;
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
