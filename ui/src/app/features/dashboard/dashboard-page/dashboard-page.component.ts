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
  readonly tabActive: 'active' = 'active';
  readonly tabApplied: 'applied' = 'applied';
  selectedTab: 'active' | 'applied' = 'active';
  jobs: JobListing[] = [];
  pendingJobs: JobListing[] = [];
  appliedJobs: JobListing[] = [];
  pendingPage = 1;
  appliedPage = 1;
  readonly jobsPerPage = 21;
  pendingSearch = '';
  appliedSearch = '';
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
    this.jobsService
      .fetchFromApi({
        pendingPage: this.pendingPage,
        appliedPage: this.appliedPage,
        pageSize: this.jobsPerPage,
        pendingSearch: this.pendingSearch,
        appliedSearch: this.appliedSearch,
      })
      .subscribe({
        next: (res) => {
          this.fetchLoading = false;
          if (res.success) {
            this.fetchError = '';
            this.pendingTotal = res.activeTotal ?? 0;
            this.appliedTotal = res.appliedTotal ?? 0;
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

  showOnboardingHint(): boolean {
    const hasResume = !!this.auth.currentUserValue?.hasResume;
    if (!hasResume) return true;
    return this.pendingTotal === 0 && this.appliedTotal === 0;
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

  selectTab(tab: 'active' | 'applied'): void {
    this.selectedTab = tab;
  }

  onPendingSearch(): void {
    this.pendingPage = 1;
    this.loadJobs();
  }

  onAppliedSearch(): void {
    this.appliedPage = 1;
    this.loadJobs();
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
    this.loadJobs();
  }

  nextPendingPage(): void {
    if (!this.canNextPending()) return;
    this.pendingPage += 1;
    this.loadJobs();
  }

  prevAppliedPage(): void {
    if (!this.canPrevApplied()) return;
    this.appliedPage -= 1;
    this.loadJobs();
  }

  nextAppliedPage(): void {
    if (!this.canNextApplied()) return;
    this.appliedPage += 1;
    this.loadJobs();
  }

}
