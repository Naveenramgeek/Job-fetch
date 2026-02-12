import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AdminStats {
  users_total: number;
  users_active: number;
  job_listings: number;
  user_job_matches: number;
  categories: number;
  admins: number;
}

export interface AdminUser {
  id: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  search_category_id: string | null;
  created_at: string | null;
}

export interface AdminUserCreate {
  email: string;
  password: string;
  is_admin?: boolean;
  is_active?: boolean;
  search_category_id?: string | null;
}

export interface AdminUserUpdate {
  email?: string;
  password?: string;
  is_admin?: boolean;
  is_active?: boolean;
  search_category_id?: string | null;
}

export interface AdminCategory {
  id: string;
  slug: string;
  display_name: string;
}

export interface AdminJobListing {
  id: string;
  job_hash: string;
  search_category_id: string;
  title: string;
  company: string;
  location: string | null;
  job_url: string;
  description: string | null;
  posted_at: string | null;
  created_at: string | null;
}

export interface AdminJobListingCreate {
  search_category_id: string;
  title: string;
  company: string;
  job_url: string;
  location?: string | null;
  description?: string | null;
  posted_at?: string | null;
}

export interface AdminJobListingUpdate {
  title?: string | null;
  company?: string | null;
  job_url?: string | null;
  location?: string | null;
  description?: string | null;
  posted_at?: string | null;
  search_category_id?: string | null;
}

export interface PipelineResult {
  collector: { total_fetched: number; total_deduped: number; inserted: number; categories: number };
  deep_match: { users: number; jobs: number; scored: number };
}

export interface PipelineStatus {
  running: boolean;
  last_run: string | null;
  next_run: string | null;
  interval_hours: number;
}

export interface AdminUsersResponse {
  items: AdminUser[];
  total: number;
}

export interface AdminJobListingsResponse {
  items: AdminJobListing[];
  total: number;
}

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly base = `${environment.apiBaseUrl}/admin`;
  private readonly jobsBase = `${environment.apiBaseUrl}/jobs`;

  constructor(private http: HttpClient) {}

  getStats(): Observable<AdminStats> {
    return this.http.get<AdminStats>(`${this.base}/stats`);
  }

  getUsers(params?: { search?: string; page?: number; page_size?: number }): Observable<AdminUsersResponse> {
    const p = params || {};
    const query: string[] = [];
    if (p.search != null && p.search !== '') query.push(`search=${encodeURIComponent(p.search)}`);
    if (p.page != null) query.push(`page=${p.page}`);
    if (p.page_size != null) query.push(`page_size=${p.page_size}`);
    const qs = query.length ? '?' + query.join('&') : '';
    return this.http.get<AdminUsersResponse>(`${this.base}/users${qs}`);
  }

  getUser(userId: string): Observable<AdminUser> {
    return this.http.get<AdminUser>(`${this.base}/users/${userId}`);
  }

  createUser(body: AdminUserCreate): Observable<AdminUser> {
    return this.http.post<AdminUser>(`${this.base}/users`, body);
  }

  updateUser(userId: string, body: AdminUserUpdate): Observable<AdminUser> {
    return this.http.patch<AdminUser>(`${this.base}/users/${userId}`, body);
  }

  deleteUser(userId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.base}/users/${userId}`);
  }

  getCategories(): Observable<AdminCategory[]> {
    return this.http.get<AdminCategory[]>(`${this.base}/categories`);
  }

  getJobListings(params?: {
    search_category_id?: string | null;
    search?: string;
    page?: number;
    page_size?: number;
  }): Observable<AdminJobListingsResponse> {
    const p = params || {};
    const query: string[] = [];
    if (p.search_category_id != null && p.search_category_id !== '') query.push(`search_category_id=${encodeURIComponent(p.search_category_id)}`);
    if (p.search != null && p.search !== '') query.push(`search=${encodeURIComponent(p.search)}`);
    if (p.page != null) query.push(`page=${p.page}`);
    if (p.page_size != null) query.push(`page_size=${p.page_size}`);
    const qs = query.length ? '?' + query.join('&') : '';
    return this.http.get<AdminJobListingsResponse>(`${this.base}/job-listings${qs}`);
  }

  getJobListing(id: string): Observable<AdminJobListing> {
    return this.http.get<AdminJobListing>(`${this.base}/job-listings/${id}`);
  }

  createJobListing(body: AdminJobListingCreate): Observable<AdminJobListing> {
    return this.http.post<AdminJobListing>(`${this.base}/job-listings`, body);
  }

  updateJobListing(id: string, body: AdminJobListingUpdate): Observable<AdminJobListing> {
    return this.http.patch<AdminJobListing>(`${this.base}/job-listings/${id}`, body);
  }

  deleteJobListing(id: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.base}/job-listings/${id}`);
  }

  deleteAllJobListings(): Observable<{ message: string; deleted: number }> {
    return this.http.delete<{ message: string; deleted: number }>(`${this.base}/job-listings`);
  }

  seedCategories(): Observable<{ message: string; categories: { slug: string; display_name: string }[] }> {
    return this.http.post<{ message: string; categories: { slug: string; display_name: string }[] }>(
      `${this.base}/seed-categories`,
      {}
    );
  }

  runPipeline(): Observable<PipelineResult> {
    return this.http.post<PipelineResult>(`${this.jobsBase}/run-pipeline`, {});
  }

  startPipeline(): Observable<{ started: boolean; message: string }> {
    return this.http.post<{ started: boolean; message: string }>(`${this.jobsBase}/start-pipeline`, {});
  }

  stopPipeline(): Observable<{ stopped: boolean; message: string }> {
    return this.http.post<{ stopped: boolean; message: string }>(`${this.jobsBase}/stop-pipeline`, {});
  }

  getPipelineStatus(): Observable<PipelineStatus> {
    return this.http.get<PipelineStatus>(`${this.jobsBase}/pipeline-status`);
  }
}
