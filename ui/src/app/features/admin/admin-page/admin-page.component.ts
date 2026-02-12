import { Component, OnInit } from '@angular/core';
import {
  AdminApiService,
  AdminStats,
  AdminUser,
  AdminUserCreate,
  AdminCategory,
  AdminJobListing,
  AdminJobListingCreate,
  PipelineStatus,
} from '../../../core/services/admin-api.service';

@Component({
  selector: 'app-admin-page',
  templateUrl: './admin-page.component.html',
  styleUrls: ['./admin-page.component.scss'],
})
export class AdminPageComponent implements OnInit {
  stats: AdminStats | null = null;
  users: AdminUser[] = [];
  categories: AdminCategory[] = [];
  jobListings: AdminJobListing[] = [];
  loading = false;
  error = '';
  pipelineError = '';
  pipelineStatus: PipelineStatus | null = null;
  startStopLoading = false;
  startStopMessage = '';
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
  deleteAllJobsLoading = false;

  constructor(private adminApi: AdminApiService) {}

  ngOnInit(): void {
    this.loadStats();
    this.loadUsers();
    this.loadPipelineStatus();
    this.loadCategories();
    this.loadJobListings();
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
    this.startStopLoading = true;
    this.pipelineError = '';
    this.startStopMessage = '';
    this.adminApi.startPipeline().subscribe({
      next: (res) => {
        this.startStopMessage = res.message;
        this.startStopLoading = false;
        this.loadPipelineStatus();
        this.loadStats();
      },
      error: (err) => {
        this.pipelineError = err.error?.detail || err.message || 'Failed to start pipeline';
        this.startStopLoading = false;
      },
    });
  }

  stopPipeline(): void {
    this.startStopLoading = true;
    this.pipelineError = '';
    this.startStopMessage = '';
    this.adminApi.stopPipeline().subscribe({
      next: (res) => {
        this.startStopMessage = res.message;
        this.startStopLoading = false;
        this.loadPipelineStatus();
      },
      error: (err) => {
        this.pipelineError = err.error?.detail || err.message || 'Failed to stop pipeline';
        this.startStopLoading = false;
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
    if (!confirm(`Delete user ${u.email}? This cannot be undone.`)) return;
    this.adminApi.deleteUser(u.id).subscribe({
      next: () => {
        this.loadStats();
        this.loadUsers();
      },
      error: (err) => {
        this.error = err.error?.detail || err.message || 'Delete failed';
      },
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

  onJobCategoryFilterChange(): void {
    this.jobPage = 1;
    this.loadJobListings();
  }

  onJobSearch(): void {
    this.jobPage = 1;
    this.loadJobListings();
  }

  onJobPageChange(page: number): void {
    this.jobPage = page;
    this.loadJobListings();
  }

  onJobPageSizeChange(): void {
    this.jobPage = 1;
    this.loadJobListings();
  }

  deleteAllJobs(): void {
    if (!confirm('Delete ALL job listings in the database? This cannot be undone.')) return;
    this.deleteAllJobsLoading = true;
    this.adminApi.deleteAllJobListings().subscribe({
      next: (res) => {
        this.deleteAllJobsLoading = false;
        this.jobListings = [];
        this.jobTotal = 0;
        this.loadStats();
      },
      error: (err) => {
        this.deleteAllJobsLoading = false;
        this.error = err.error?.detail || err.message || 'Delete all failed';
      },
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
        },
        error: (err) => {
          this.jobFormError = err.error?.detail || err.message || 'Create failed';
          this.jobSaveLoading = false;
        },
      });
    }
  }

  deleteJob(j: AdminJobListing): void {
    if (!confirm(`Delete job listing "${j.title}" at ${j.company}?`)) return;
    this.adminApi.deleteJobListing(j.id).subscribe({
      next: () => {
        this.loadStats();
        this.loadJobListings();
      },
      error: (err) => {
        this.error = err.error?.detail || err.message || 'Delete failed';
      },
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
}
