import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { JobListing, ApplicationStatus } from '../../models/job.model';
import { JobsApiService, JobMatchResultDto, TailoredResumeDto } from './jobs-api.service';

function dtoToListing(d: JobMatchResultDto, status: ApplicationStatus): JobListing {
  const appliedAt = d.applied_at ? d.applied_at.slice(0, 10) : undefined;
  return {
    id: d.id,
    title: d.title,
    company: d.company,
    location: d.location ?? undefined,
    jobUrl: d.job_url,
    status,
    postedAt: d.posted_at ?? undefined,
    createdAt: d.created_at ?? undefined,
    appliedAt: status === 'applied' ? appliedAt : undefined,
    matchScore: d.match_score,
    matchReason: d.match_reason ?? undefined,
    resumeYearsExperience: d.resume_years_experience ?? undefined,
    description: d.description ?? undefined,
  };
}

@Injectable({ providedIn: 'root' })
export class JobsService {
  private jobs$ = new BehaviorSubject<JobListing[]>([]);

  constructor(private jobsApi: JobsApiService) {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        this.onTabVisible();
      }
    });
  }

  get jobs(): Observable<JobListing[]> {
    return this.jobs$.asObservable();
  }

  get jobsValue(): JobListing[] {
    return this.jobs$.value;
  }

  private setJobs(active: JobMatchResultDto[], applied: JobMatchResultDto[]): void {
    const listings: JobListing[] = [
      ...active.map((d) => dtoToListing(d, 'pending')),
      ...applied.map((d) => dtoToListing(d, 'applied')),
    ];
    this.jobs$.next(listings);
  }

  updateStatus(jobId: string, status: 'applied' | 'not_applied'): void {
    this.jobsApi.updateStatus(jobId, status).subscribe({
      next: () => this.refreshFromApi(),
      error: () => {},
    });
  }

  removeJob(jobId: string): void {
    this.updateStatus(jobId, 'not_applied');
  }

  /** Permanently delete a job from the user's list (e.g. old jobs). */
  deleteJob(jobId: string): void {
    this.jobsApi.deleteMatch(jobId).subscribe({
      next: () => this.refreshFromApi(),
      error: () => {},
    });
  }

  tailorResume(jobId: string): Observable<TailoredResumeDto> {
    return this.jobsApi.tailorResume(jobId);
  }

  tailorResumeFromJd(jobDescription: string, jobTitle?: string): Observable<TailoredResumeDto> {
    return this.jobsApi.tailorResumeFromJd(jobDescription, jobTitle);
  }

  renderLatexPdf(latex: string): Observable<Blob> {
    return this.jobsApi.renderLatexPdf(latex);
  }

  // Track last opened job for "Did you apply?" dialog
  private lastOpenedJobId: string | null = null;
  private onVisibilityCallback: ((jobId: string) => void) | null = null;

  setOnReturnCallback(cb: (jobId: string) => void): void {
    this.onVisibilityCallback = cb;
  }

  openJobAndTrack(job: JobListing): void {
    this.lastOpenedJobId = job.id;
    window.open(job.jobUrl, '_blank', 'noopener,noreferrer');
  }

  private onTabVisible(): void {
    if (this.lastOpenedJobId && this.onVisibilityCallback) {
      const jobId = this.lastOpenedJobId;
      this.lastOpenedJobId = null;
      const job = this.jobsValue.find((j) => j.id === jobId);
      if (job && job.status === 'pending') {
        this.onVisibilityCallback(jobId);
      }
    }
  }

  clearLastOpened(): void {
    this.lastOpenedJobId = null;
  }

  /** Fetch LLM-matched jobs from backend (active + applied). */
  fetchFromApi(): Observable<{ success: boolean; error?: string; count?: number }> {
    return new Observable((obs) => {
      this.jobsApi.getJobs().subscribe({
        next: (res) => {
          this.setJobs(res.active, res.applied);
          obs.next({ success: true, count: res.active.length + res.applied.length });
          obs.complete();
        },
        error: (err) => {
          const msg = err.error?.detail || err.message || 'Failed to fetch jobs';
          obs.next({ success: false, error: msg });
          obs.complete();
        },
      });
    });
  }

  private refreshFromApi(): void {
    this.jobsApi.getJobs().subscribe({
      next: (res) => this.setJobs(res.active, res.applied),
    });
  }
}
