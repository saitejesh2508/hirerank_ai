export type User = {
  id: number;
  email: string;
  full_name: string;
  role: "recruiter" | "client";
  organization_id: number | null;
};

export type Criterion = {
  criterion: string;
  status: string;
  score: number;
  quotation: string;
  explanation: string;
  confidence: number;
};

export type Candidate = {
  id: number;
  external_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  current_role: string | null;
  experience_years: number | null;
  notice_days: number | null;
  location: string | null;
  skills: string[];
  education: string[];
  employers: string[];
  missing_information: string[];
  score: {
    overall_score: number;
    category: string;
    scoring_method: string;
    warnings: string[];
    criteria: Criterion[];
  } | null;
  synthetic?: boolean;
  status?: string;
  submission_id?: number;
  requisition_id?: number;
  requisition_title?: string;
  resume_text?: string;
  resume_filename?: string;
};

export type Requisition = {
  id: number;
  title: string;
  organization_id: number;
  organization: string;
  description: string;
  location: string | null;
  min_experience: number | null;
  max_experience: number | null;
  required_skills: string[];
  preferred_skills: string[];
  max_notice_days: number | null;
  min_ctc: number | null;
  max_ctc: number | null;
  scorecard_approved: boolean;
  status: string;
  candidate_count?: number;
  screened_count?: number;
};
