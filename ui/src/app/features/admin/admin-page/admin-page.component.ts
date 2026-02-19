import { Component, OnInit } from '@angular/core';
import {
  AdminApiService,
  AdminStats,
  AdminUser,
  AdminUserCreate,
  AdminCategory,
  AdminJobListing,
  AdminJobListingCreate,
  AdminFeedbackItem,
  PipelineStatus,
} from '../../../core/services/admin-api.service';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmActionDialogComponent } from '../confirm-action-dialog/confirm-action-dialog.component';

@Component({
  selector: 'app-admin-page',
  templateUrl: './admin-page.component.html',
  styleUrls: ['./admin-page.component.scss'],
})
export class AdminPageComponent implements OnInit {
  readonly tabUsers: 'users' = 'users';
  readonly tabJobs: 'jobs' = 'jobs';
  readonly tabOldJobs: 'old_jobs' = 'old_jobs';
  readonly tabFeedback: 'feedback' = 'feedback';
  selectedTab: 'users' | 'jobs' | 'old_jobs' | 'feedback' = 'users';
  stats: AdminStats | null = null;
  users: AdminUser[] = [];
  categories: AdminCategory[] = [];
  jobListings: AdminJobListing[] = [];
  oldJobListings: AdminJobListing[] = [];
  feedbackItems: AdminFeedbackItem[] = [];
  loading = false;
  error = '';
  pipelineError = '';
  pipelineRunLoading = false;
  pipelineRunMessage = '';
  advancedPanelOpen = false;
  pipelineStatus: PipelineStatus | null = null;
  recurringLoading = false;
  recurringMessage = '';
  seedLoading = false;
  seedMessage = '';

  // User form
  showUserForm = false;
  editingUserId: string | null = null;
  userForm = { email: '', password: '', is_admin: false, is_active: true, search_category_id: null as string | null };
  userSaveLoading = false;
  userFormError = '';

  // Job listing form
  showJobForm = false;
  editingJobId: string | null = null;
  jobForm: AdminJobListingCreate = {
    search_category_id: '',
    title: '',
    company: '',
    job_url: '',
    location: null,
    description: null,
    posted_at: null,
  };
  jobSaveLoading = false;
  jobFormError = '';
  jobCategoryFilter: string | null = null;

  // Pagination & search
  userSearch = '';
  userPage = 1;
  userPageSize = 20;
  userTotal = 0;
  jobSearch = '';
  jobPage = 1;
  jobPageSize = 20;
  jobTotal = 0;
  oldJobPage = 1;
  oldJobPageSize = 20;
  oldJobTotal = 0;
  deleteAllJobsLoading = false;
  deleteOldJobsLoading = false;
  feedbackSearch = '';
  feedbackPage = 1;
  feedbackPageSize = 20;
  feedbackTotal = 0;

  constructor(
    private adminApi: AdminApiService,
    private dialog: MatDialog,
  ) {}

  ngOnInit(): void {
    this.loadStats();
    this.loadUsers();
    this.loadPipelineStatus();
    this.loadCategories();
    this.loadJobListings();
    this.loadOldJobListings();
    this.loadFeedback();
  }

  selectTab(tab: 'users' | 'jobs' | 'old_jobs' | 'feedback'): void {
    this.selectedTab = tab;
  }

  toggleAdvancedPanel(): void {
    this.advancedPanelOpen = !this.advancedPanelOpen;
    if (this.advancedPanelOpen) {
      this.loadPipelineStatus();
    }
  }

  loadPipelineStatus(): void {
    this.adminApi.getPipelineStatus().subscribe({
      next: (s) => (this.pipelineStatus = s),
      error: () => (this.pipelineStatus = null),
    });
  }

  loadStats(): void {
    this.loading = true;
    this.error = '';
    this.adminApi.getStats().subscribe({
      next: (s) => {
        this.stats = s;
        this.loading = false;
      },
      error: (err) => {
        this.error = err.error?.detail || err.message || 'Failed to load stats';
        this.loading = false;
      },
    });
  }

  loadUsers(): void {
    this.adminApi
      .getUsers({ search: this.userSearch || undefined, page: this.userPage, page_size: this.userPageSize })
      .subscribe({
        next: (res) => {
          this.users = res.items;
          this.userTotal = res.total;
        },
        error: (err) => {
          if (!this.error) this.error = err.error?.detail || err.message || 'Failed to load users';
        },
      });
  }

  onUserSearch(): void {
    this.userPage = 1;
    this.loadUsers();
  }

  onUserPageChange(page: number): void {
    this.userPage = page;
    this.loadUsers();
  }

  onUserPageSizeChange(): void {
    this.userPage = 1;
    this.loadUsers();
  }

  runPipeline(): void {
    this.pipelineRunLoading = true;
    this.pipelineError = '';
    this.pipelineRunMessage = '';
    this.adminApi.runPipeline().subscribe({
      next: () => {
        this.pipelineRunMessage = 'Pipeline run completed successfully.';
        this.pipelineRunLoading = false;
        this.loadStats();
        this.loadPipelineStatus();
        this.loadJobListings();
        this.loadOldJobListings();
      },
      error: (err) => {
        this.pipelineError = err.error?.detail || err.message || 'Failed to start pipeline';
        this.pipelineRunLoading = false;
      },
    });
  }

  startRecurringPipeline(): void {
    this.recurringLoading = true;
    this.pipelineError = '';
    this.recurringMessage = '';
    this.adminApi.startPipeline().subscribe({
      next: (res) => {
        this.recurringLoading = false;
        this.recurringMessage = res.message;
        this.loadPipelineStatus();
      },
      error: (err) => {
        this.recurringLoading = false;
        this.pipelineError = err.error?.detail || err.message || 'Failed to start recurring pipeline';
      },
    });
  }

  stopRecurringPipeline(): void {
    this.recurringLoading = true;
    this.pipelineError = '';
    this.recurringMessage = '';
    this.adminApi.stopPipeline().subscribe({
      next: (res) => {
        this.recurringLoading = false;
        this.recurringMessage = res.message;
        this.loadPipelineStatus();
      },
      error: (err) => {
        this.recurringLoading = false;
        this.pipelineError = err.error?.detail || err.message || 'Failed to stop recurring pipeline';
      },
    });
  }

  seedCategories(): void {
    this.seedLoading = true;
    this.seedMessage = '';
    this.pipelineError = '';
    this.adminApi.seedCategories().subscribe({
      next: (res) => {
        this.seedMessage = res.message;
        this.seedLoading = false;
        this.loadStats();
      },
      error: (err) => {
        const detail = err.error?.detail ?? err.error?.message ?? err.message ?? 'Seed failed';
        this.seedMessage = typeof detail === 'string' ? detail : JSON.stringify(detail);
        this.seedLoading = false;
      },
    });
  }

  toggleAdmin(user: AdminUser): void {
    this.adminApi.updateUser(user.id, { is_admin: !user.is_admin }).subscribe({
      next: (updated) => {
        user.is_admin = updated.is_admin;
      },
      error: (err) => {
        this.error = err.error?.detail || err.message || 'Update failed';
      },
    });
  }

  toggleActive(user: AdminUser): void {
    this.adminApi.updateUser(user.id, { is_active: !user.is_active }).subscribe({
      next: (updated) => {
        user.is_active = updated.is_active;
      },
      error: (err) => {
        this.error = err.error?.detail || err.message || 'Update failed';
      },
    });
  }

  openAddUser(): void {
    this.editingUserId = null;
    this.userForm = { email: '', password: '', is_admin: false, is_active: true, search_category_id: null };
    this.userFormError = '';
    this.showUserForm = true;
  }

  openEditUser(u: AdminUser): void {
    this.editingUserId = u.id;
    this.userForm = {
      email: u.email,
      password: '',
      is_admin: u.is_admin,
      is_active: u.is_active,
      search_category_id: u.search_category_id ?? null,
    };
    this.userFormError = '';
    this.showUserForm = true;
  }

  cancelUserForm(): void {
    this.showUserForm = false;
    this.editingUserId = null;
  }

  saveUser(): void {
    this.userSaveLoading = true;
    this.userFormError = '';
    if (this.editingUserId) {
      const body: { email?: string; password?: string; is_admin?: boolean; is_active?: boolean; search_category_id?: string | null } = {
        email: this.userForm.email,
        is_admin: this.userForm.is_admin,
        is_active: this.userForm.is_active,
        search_category_id: this.userForm.search_category_id,
      };
      if (this.userForm.password) body.password = this.userForm.password;
      this.adminApi.updateUser(this.editingUserId, body).subscribe({
        next: (updated) => {
          const idx = this.users.findIndex((x) => x.id === updated.id);
          if (idx >= 0) this.users[idx] = updated;
          this.userSaveLoading = false;
          this.showUserForm = false;
          this.editingUserId = null;
          this.loadStats();
        },
        error: (err) => {
          this.userFormError = err.error?.detail || err.message || 'Update failed';
          this.userSaveLoading = false;
        },
      });
    } else {
      const body: AdminUserCreate = {
        email: this.userForm.email,
        password: this.userForm.password,
        is_admin: this.userForm.is_admin,
        is_active: this.userForm.is_active,
        search_category_id: this.userForm.search_category_id,
      };
      this.adminApi.createUser(body).subscribe({
        next: () => {
          this.userSaveLoading = false;
          this.showUserForm = false;
          this.loadStats();
          this.loadUsers();
        },
        error: (err) => {
          this.userFormError = err.error?.detail || err.message || 'Create failed';
          this.userSaveLoading = false;
        },
      });
    }
  }

  deleteUser(u: AdminUser): void {
    this.openConfirmDialog({
      title: 'Delete user',
      message: `Delete user ${u.email}? This cannot be undone.`,
      confirmText: 'Delete user',
      isDanger: true,
    }).afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.adminApi.deleteUser(u.id).subscribe({
        next: () => {
          this.loadStats();
          this.loadUsers();
        },
        error: (err) => {
          this.error = err.error?.detail || err.message || 'Delete failed';
        },
      });
    });
  }

  loadCategories(): void {
    this.adminApi.getCategories().subscribe({
      next: (c) => (this.categories = c),
      error: () => (this.categories = []),
    });
  }

  loadJobListings(): void {
    this.adminApi
      .getJobListings({
        search_category_id: this.jobCategoryFilter ?? undefined,
        search: this.jobSearch || undefined,
        page: this.jobPage,
        page_size: this.jobPageSize,
      })
      .subscribe({
        next: (res) => {
          this.jobListings = res.items;
          this.jobTotal = res.total;
        },
        error: () => (this.jobListings = []),
      });
  }

  loadOldJobListings(): void {
    this.adminApi
      .getOldJobListings({
        search_category_id: this.jobCategoryFilter ?? undefined,
        search: this.jobSearch || undefined,
        page: this.oldJobPage,
        page_size: this.oldJobPageSize,
      })
      .subscribe({
        next: (res) => {
          this.oldJobListings = res.items;
          this.oldJobTotal = res.total;
        },
        error: () => (this.oldJobListings = []),
      });
  }

  loadFeedback(): void {
    this.adminApi
      .getFeedback({
        search: this.feedbackSearch || undefined,
        page: this.feedbackPage,
        page_size: this.feedbackPageSize,
      })
      .subscribe({
        next: (res) => {
          this.feedbackItems = res.items;
          this.feedbackTotal = res.total;
        },
        error: () => {
          this.feedbackItems = [];
          this.feedbackTotal = 0;
        },
      });
  }

  onFeedbackSearch(): void {
    this.feedbackPage = 1;
    this.loadFeedback();
  }

  onFeedbackPageChange(page: number): void {
    this.feedbackPage = page;
    this.loadFeedback();
  }

  onFeedbackPageSizeChange(): void {
    this.feedbackPage = 1;
    this.loadFeedback();
  }

  onJobCategoryFilterChange(): void {
    this.jobPage = 1;
    this.oldJobPage = 1;
    this.loadJobListings();
    this.loadOldJobListings();
  }

  onJobSearch(): void {
    this.jobPage = 1;
    this.oldJobPage = 1;
    this.loadJobListings();
    this.loadOldJobListings();
  }

  onJobPageChange(page: number): void {
    this.jobPage = page;
    this.loadJobListings();
  }

  onJobPageSizeChange(): void {
    this.jobPage = 1;
    this.loadJobListings();
  }

  onOldJobPageChange(page: number): void {
    this.oldJobPage = page;
    this.loadOldJobListings();
  }

  onOldJobPageSizeChange(): void {
    this.oldJobPage = 1;
    this.loadOldJobListings();
  }

  deleteAllJobs(): void {
    this.openConfirmDialog({
      title: 'Delete all job listings',
      message: 'Delete all job listings in the database? This cannot be undone.',
      confirmText: 'Delete all',
      isDanger: true,
    }).afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.deleteAllJobsLoading = true;
      this.adminApi.deleteAllJobListings().subscribe({
        next: () => {
          this.deleteAllJobsLoading = false;
          this.jobListings = [];
          this.jobTotal = 0;
          this.oldJobListings = [];
          this.oldJobTotal = 0;
          this.loadStats();
        },
        error: (err) => {
          this.deleteAllJobsLoading = false;
          this.error = err.error?.detail || err.message || 'Delete all failed';
        },
      });
    });
  }

  deleteOldJobs(): void {
    this.openConfirmDialog({
      title: 'Delete old jobs',
      message: 'Delete all job listings older than 24 hours? This cannot be undone.',
      confirmText: 'Delete old jobs',
      isDanger: true,
    }).afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.deleteOldJobsLoading = true;
      this.adminApi.deleteOldJobListings().subscribe({
        next: () => {
          this.deleteOldJobsLoading = false;
          this.loadStats();
          this.loadJobListings();
          this.loadOldJobListings();
        },
        error: (err) => {
          this.deleteOldJobsLoading = false;
          this.error = err.error?.detail || err.message || 'Delete old jobs failed';
        },
      });
    });
  }

  openAddJob(): void {
    this.editingJobId = null;
    this.jobForm = {
      search_category_id: this.categories[0]?.id ?? '',
      title: '',
      company: '',
      job_url: '',
      location: null,
      description: null,
      posted_at: null,
    };
    this.jobFormError = '';
    this.showJobForm = true;
  }

  openEditJob(j: AdminJobListing): void {
    this.editingJobId = j.id;
    this.jobForm = {
      search_category_id: j.search_category_id,
      title: j.title,
      company: j.company,
      job_url: j.job_url,
      location: j.location ?? null,
      description: j.description ?? null,
      posted_at: j.posted_at ?? null,
    };
    this.jobFormError = '';
    this.showJobForm = true;
  }

  cancelJobForm(): void {
    this.showJobForm = false;
    this.editingJobId = null;
  }

  saveJob(): void {
    this.jobSaveLoading = true;
    this.jobFormError = '';
    if (this.editingJobId) {
      this.adminApi
        .updateJobListing(this.editingJobId, {
          search_category_id: this.jobForm.search_category_id,
          title: this.jobForm.title,
          company: this.jobForm.company,
          job_url: this.jobForm.job_url,
          location: this.jobForm.location,
          description: this.jobForm.description,
          posted_at: this.jobForm.posted_at,
        })
        .subscribe({
          next: () => {
            this.jobSaveLoading = false;
            this.showJobForm = false;
            this.editingJobId = null;
            this.loadStats();
            this.loadJobListings();
            this.loadOldJobListings();
          },
          error: (err) => {
            this.jobFormError = err.error?.detail || err.message || 'Update failed';
            this.jobSaveLoading = false;
          },
        });
    } else {
      this.adminApi.createJobListing(this.jobForm).subscribe({
        next: () => {
          this.jobSaveLoading = false;
          this.showJobForm = false;
          this.loadStats();
          this.loadJobListings();
          this.loadOldJobListings();
        },
        error: (err) => {
          this.jobFormError = err.error?.detail || err.message || 'Create failed';
          this.jobSaveLoading = false;
        },
      });
    }
  }

  deleteJob(j: AdminJobListing): void {
    this.openConfirmDialog({
      title: 'Delete job listing',
      message: `Delete job listing "${j.title}" at ${j.company}?`,
      confirmText: 'Delete listing',
      isDanger: true,
    }).afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.adminApi.deleteJobListing(j.id).subscribe({
        next: () => {
          this.loadStats();
          this.loadJobListings();
          this.loadOldJobListings();
        },
        error: (err) => {
          this.error = err.error?.detail || err.message || 'Delete failed';
        },
      });
    });
  }

  formatDate(s: string | null): string {
    if (!s) return '-';
    return new Date(s).toLocaleString();
  }

  categoryDisplay(id: string): string {
    const c = this.categories.find((x) => x.id === id);
    return c ? c.display_name : id;
  }

  /** For template: show "X–Y of total" pagination range. */
  min(a: number, b: number): number {
    return Math.min(a, b);
  }

  private openConfirmDialog(data: {
    title: string;
    message: string;
    confirmText?: string;
    isDanger?: boolean;
  }) {
    return this.dialog.open(ConfirmActionDialogComponent, {
      width: '420px',
      disableClose: false,
      data: {
        title: data.title,
        message: data.message,
        confirmText: data.confirmText || 'Confirm',
        cancelText: 'Cancel',
        isDanger: data.isDanger ?? false,
      },
    });
  }
}
