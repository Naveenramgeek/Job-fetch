import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { AuthService } from '../../../core/services/auth.service';
import { JobsService } from '../../../core/services/jobs.service';
import { JobListing } from '../../../models/job.model';
import { ApplicationStatusDialogComponent } from '../application-status-dialog/application-status-dialog.component';

@Component({
  selector: 'app-dashboard-page',
  templateUrl: './dashboard-page.component.html',
  styleUrls: ['./dashboard-page.component.scss'],
})
export class DashboardPageComponent implements OnInit, OnDestroy {
  jobs: JobListing[] = [];
  private pendingJobs: JobListing[] = [];
  private appliedJobs: JobListing[] = [];
  jobListings: JobListing[] = [];
  appliedByDate: { date: string; jobs: JobListing[] }[] = [];
  pendingPage = 1;
  appliedPage = 1;
  readonly jobsPerPage = 6;
  pendingTotal = 0;
  appliedTotal = 0;
  fetchLoading = false;
  fetchError = '';
  private destroy$ = new Subject<void>();

  constructor(
    public auth: AuthService,
    private jobsService: JobsService,
    private router: Router,
    private dialog: MatDialog,
  ) {}

  ngOnInit(): void {
    this.loadJobs();
    this.jobsService.jobs.pipe(takeUntil(this.destroy$)).subscribe((j) => {
      this.jobs = j;
      this.pendingJobs = j.filter((job) => job.status === 'pending');
      this.appliedJobs = j.filter((job) => job.status === 'applied');
      this.refreshPagination();
    });

    this.jobsService.setOnReturnCallback((jobId) => {
      this.showApplicationStatusDialog(jobId);
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  openJob(job: JobListing): void {
    this.jobsService.openJobAndTrack(job);
  }

  tailorResume(job: JobListing, event: Event): void {
    event.stopPropagation();
    this.router.navigate(['/dashboard/tailor', job.id], {
      queryParams: { title: job.title, company: job.company },
    });
  }

  loadJobs(): void {
    this.fetchError = '';
    this.fetchLoading = true;
    this.jobsService.fetchFromApi().subscribe({
      next: (res) => {
        this.fetchLoading = false;
        if (res.success) {
          this.fetchError = '';
        } else {
          this.fetchError = res.error ?? 'Failed to fetch jobs';
        }
      },
      error: () => {
        this.fetchLoading = false;
        this.fetchError = 'Failed to fetch jobs';
      },
    });
  }

  fetchJobs(): void {
    this.loadJobs();
  }

  matchScorePercent(job: JobListing): string {
    if (job.matchScore == null) return '';
    return Math.round(job.matchScore * 100) + '% match';
  }

  markStatus(job: JobListing, status: 'applied' | 'not_applied', event?: Event): void {
    if (event) event.stopPropagation();
    this.jobsService.updateStatus(job.id, status); // Persists to DB, removes from active
  }

  skipJob(job: JobListing, event?: Event): void {
    if (event) event.stopPropagation();
    this.jobsService.removeJob(job.id);
  }

  /** Check if job was collected more than 24 hours ago. */
  isOlderThan24h(job: JobListing): boolean {
    if (!job.createdAt) return false;
    const created = new Date(job.createdAt).getTime();
    return Date.now() - created > 24 * 60 * 60 * 1000;
  }

  deleteJob(job: JobListing, event?: Event): void {
    if (event) event.stopPropagation();
    this.jobsService.deleteJob(job.id);
  }

  formatDate(dateStr: string): string {
    if (!dateStr || dateStr === 'Unknown') return dateStr;
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  }

  showApplicationStatusDialog(jobId: string): void {
    const job = this.jobs.find((j) => j.id === jobId);
    if (!job) return;

    const dialogRef = this.dialog.open(ApplicationStatusDialogComponent, {
      data: { job },
      width: '400px',
      disableClose: false,
    });

    dialogRef.afterClosed().subscribe((result: 'applied' | 'not_applied' | undefined) => {
      if (result) {
        this.jobsService.updateStatus(jobId, result);
      }
    });
  }

  goToResume(): void {
    this.router.navigate(['/resume']);
  }

  pendingTotalPages(): number {
    return Math.max(1, Math.ceil(this.pendingTotal / this.jobsPerPage));
  }

  appliedTotalPages(): number {
    return Math.max(1, Math.ceil(this.appliedTotal / this.jobsPerPage));
  }

  canPrevPending(): boolean {
    return this.pendingPage > 1;
  }

  canNextPending(): boolean {
    return this.pendingPage < this.pendingTotalPages();
  }

  canPrevApplied(): boolean {
    return this.appliedPage > 1;
  }

  canNextApplied(): boolean {
    return this.appliedPage < this.appliedTotalPages();
  }

  prevPendingPage(): void {
    if (!this.canPrevPending()) return;
    this.pendingPage -= 1;
    this.refreshPagination();
  }

  nextPendingPage(): void {
    if (!this.canNextPending()) return;
    this.pendingPage += 1;
    this.refreshPagination();
  }

  prevAppliedPage(): void {
    if (!this.canPrevApplied()) return;
    this.appliedPage -= 1;
    this.refreshPagination();
  }

  nextAppliedPage(): void {
    if (!this.canNextApplied()) return;
    this.appliedPage += 1;
    this.refreshPagination();
  }

  private refreshPagination(): void {
    this.pendingTotal = this.pendingJobs.length;
    const pendingPages = this.pendingTotalPages();
    this.pendingPage = Math.min(Math.max(this.pendingPage, 1), pendingPages);
    const pendingStart = (this.pendingPage - 1) * this.jobsPerPage;
    this.jobListings = this.pendingJobs.slice(pendingStart, pendingStart + this.jobsPerPage);

    this.appliedTotal = this.appliedJobs.length;
    const appliedPages = this.appliedTotalPages();
    this.appliedPage = Math.min(Math.max(this.appliedPage, 1), appliedPages);
    const appliedStart = (this.appliedPage - 1) * this.jobsPerPage;
    const appliedPageJobs = this.appliedJobs.slice(appliedStart, appliedStart + this.jobsPerPage);
    this.appliedByDate = this.groupAppliedByDate(appliedPageJobs);
  }

  private groupAppliedByDate(applied: JobListing[]): { date: string; jobs: JobListing[] }[] {
    const byDate = new Map<string, JobListing[]>();
    applied.forEach((job) => {
      const d = job.appliedAt || 'Unknown';
      if (!byDate.has(d)) byDate.set(d, []);
      byDate.get(d)!.push(job);
    });
    return Array.from(byDate.entries())
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([date, jobs]) => ({ date, jobs }));
  }

}
