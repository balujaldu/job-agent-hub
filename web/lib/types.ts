export type JobStatus =
  | "queued"
  | "processing"
  | "awaiting_approval"
  | "email_not_found"
  | "approved"
  | "sending"
  | "sent"
  | "failed"
  | "terminated";

export type Provenance = "original" | "reworded" | "inferred";

export interface JobSummary {
  id: number;
  status: JobStatus;
  company: string;
  role: string;
  to_email: string;
  ats_before: number | null;
  ats_after: number | null;
  error: string;
  created_at: string;
  sent_at: string | null;
}

export interface ATSDetail {
  score: number;
  keyword_score: number;
  format_score: number;
  matched: string[];
  missing: string[];
  format_issues: string[];
}

export interface TailoredBullet {
  text: string;
  provenance: Provenance;
}

export interface TailoredResume {
  name: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  skills: { name: string; provenance: Provenance }[];
  experience: {
    company: string;
    title: string;
    location: string;
    start: string;
    end: string;
    bullets: TailoredBullet[];
  }[];
  projects: { name: string; description: string; bullets: TailoredBullet[] }[];
  education: { institution: string; degree: string; field: string; start: string; end: string }[];
  certifications: string[];
}

export interface AgentEvent {
  id: number;
  agent: string;
  level: "info" | "warn" | "error";
  message: string;
  at: string;
}

export interface JobDetail extends JobSummary {
  source_type: "screenshot" | "text";
  source_text: string;
  has_screenshot: boolean;
  location: string;
  company_website: string;
  job_url: string;
  jd_text: string;
  keywords: string[];
  recruiter_name: string;
  email_source: string;
  email_subject: string;
  email_body: string;
  tailored: TailoredResume | null;
  has_pdf: boolean;
  ats_before_detail: ATSDetail | null;
  ats_after_detail: ATSDetail | null;
  events: AgentEvent[];
}

export interface ResumeData {
  name: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  skills: string[];
  experience: { company: string; title: string; location: string; start: string; end: string; bullets: string[] }[];
  education: { institution: string; degree: string; field: string; start: string; end: string; details: string }[];
  projects: { name: string; description: string; bullets: string[] }[];
  certifications: string[];
}

export interface BaseResume {
  id: number;
  filename: string;
  data: ResumeData;
  extra_skills: string[];
  extra_notes: string;
  confirmed: boolean;
}

export interface AppSettings {
  sending_paused: boolean;
  gmail: { configured: boolean; address: string; redirect_uri: string };
  model: string;
}

export const ACTIVE_STATUSES: JobStatus[] = ["queued", "processing", "approved", "sending"];
