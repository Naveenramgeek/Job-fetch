export type ApplicationStatus = 'pending' | 'applied' | 'not_applied';

export interface JobListing {
  id: string;
  title: string;
  company: string;
  location?: string;
  jobUrl: string;
  status: ApplicationStatus;
  postedAt?: string;
  createdAt?: string;  // When collected; used for age badge (e.g. "Older than 24h")
  appliedAt?: string;
  /** Match score 0–1 from resume vs JD (LLM); only for jobs fetched from API */
  matchScore?: number;
  matchReason?: string;
  resumeYearsExperience?: number;
  /** Job description text from the listing */
  description?: string;
}

export interface JobFetchParams {
  search_term?: string;
  location?: string;
  results_wanted?: number;
  hours_old?: number;
}
