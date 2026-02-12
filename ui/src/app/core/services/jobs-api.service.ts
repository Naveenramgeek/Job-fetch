import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface JobMatchResultDto {
  id: string;
  title: string;
  company: string;
  location: string | null;
  job_url: string;
  description: string | null;
  site: string | null;
  posted_at: string | null;
  created_at: string | null;
  match_score: number;
  match_reason: string | null;
  resume_years_experience?: number | null;
  applied_at?: string | null;
}

export interface JobsResponseDto {
  active: JobMatchResultDto[];
  applied: JobMatchResultDto[];
}

export interface TailoredResumeDto {
  match_id: string;
  job_title: string;
  company: string;
  latex: string;
}

@Injectable({ providedIn: 'root' })
export class JobsApiService {
  private readonly base = `${environment.apiBaseUrl}/jobs`;

  constructor(private http: HttpClient) {}

  /** Get LLM-matched jobs for the user (active + applied). */
  getJobs(): Observable<JobsResponseDto> {
    return this.http.get<JobsResponseDto>(this.base);
  }

  /** Get active (pending) jobs only. */
  getMatched(status: 'pending' = 'pending'): Observable<JobMatchResultDto[]> {
    return this.http.get<JobMatchResultDto[]>(`${this.base}/matched`, { params: { status } });
  }

  /** Update job status (applied or not_applied). */
  updateStatus(matchId: string, status: 'applied' | 'not_applied'): Observable<JobMatchResultDto> {
    return this.http.patch<JobMatchResultDto>(`${this.base}/matches/${matchId}`, { status });
  }

  /** Delete a job from the user's list (removes permanently). */
  deleteMatch(matchId: string): Observable<{ deleted: boolean }> {
    return this.http.delete<{ deleted: boolean }>(`${this.base}/matches/${matchId}`);
  }

  /** Generate tailored resume LaTeX for a job match. */
  tailorResume(matchId: string): Observable<TailoredResumeDto> {
    return this.http.post<TailoredResumeDto>(`${this.base}/matches/${matchId}/tailor-resume`, {});
  }

  /** Generate tailored resume LaTeX from user-entered JD text. */
  tailorResumeFromJd(jobDescription: string, jobTitle?: string): Observable<TailoredResumeDto> {
    return this.http.post<TailoredResumeDto>(`${this.base}/tailor-resume-from-jd`, {
      job_description: jobDescription,
      job_title: jobTitle || null,
    });
  }

  /** Render LaTeX into PDF for in-app preview. */
  renderLatexPdf(latex: string): Observable<Blob> {
    return this.http.post(`${this.base}/render-latex-pdf`, { latex }, { responseType: 'blob' });
  }
}
