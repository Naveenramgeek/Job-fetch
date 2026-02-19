import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable } from 'rxjs';

import { AuthApiService, AuthResponse, ProfileUpdateRequest, UserResponse } from './auth-api.service';

export interface User {
  id: string;
  email: string;
  name: string;
  hasResume?: boolean;
  isAdmin?: boolean;
  requiresPasswordChange?: boolean;
}

const TOKEN_KEY = 'jobfetch_token';
const USER_KEY = 'jobfetch_user';

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp as number | undefined;
    if (!exp) return true;
    return Date.now() >= exp * 1000;
  } catch {
    return true;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private currentUser$ = new BehaviorSubject<User | null>(this.loadUser());

  constructor(
    private router: Router,
    private authApi: AuthApiService,
  ) {}

  get user(): Observable<User | null> {
    return this.currentUser$.asObservable();
  }

  get isAuthenticated(): boolean {
    return this.currentUser$.value !== null;
  }

  get currentUserValue(): User | null {
    return this.currentUser$.value;
  }

  get requiresPasswordChange(): boolean {
    return this.currentUser$.value?.requiresPasswordChange ?? false;
  }

  get token(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  private loadUser(): User | null {
    try {
      // One-time migration from localStorage to sessionStorage for safer token handling.
      const legacyToken = localStorage.getItem(TOKEN_KEY);
      const legacyUser = localStorage.getItem(USER_KEY);
      if (!sessionStorage.getItem(TOKEN_KEY) && legacyToken) {
        sessionStorage.setItem(TOKEN_KEY, legacyToken);
        localStorage.removeItem(TOKEN_KEY);
      }
      if (!sessionStorage.getItem(USER_KEY) && legacyUser) {
        sessionStorage.setItem(USER_KEY, legacyUser);
        localStorage.removeItem(USER_KEY);
      }
      const token = sessionStorage.getItem(TOKEN_KEY);
      const stored = sessionStorage.getItem(USER_KEY);
      if (!token || !stored) return null;
      if (isTokenExpired(token)) {
        this.clearStoredAuth();
        return null;
      }
      return JSON.parse(stored) as User;
    } catch {
      return null;
    }
  }

  private clearStoredAuth(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  setAuthFromResponse(res: AuthResponse): void {
    sessionStorage.setItem(TOKEN_KEY, res.access_token);
    const user: User = {
      id: res.user.id,
      email: res.user.email,
      name: res.user.email.split('@')[0],
      hasResume: res.user.has_resume,
      isAdmin: res.user.is_admin ?? false,
      requiresPasswordChange: res.user.requires_password_change ?? false,
    };
    this.currentUser$.next(user);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  login(email: string, password: string): Observable<{ success: boolean; error?: string }> {
    return new Observable((obs) => {
      this.authApi.login({ email, password }).subscribe({
        next: (res) => {
          this.setAuthFromResponse(res);
          obs.next({ success: true });
          obs.complete();
        },
        error: (err) => {
          obs.next({
            success: false,
            error: err.error?.detail || err.message || 'Login failed',
          });
          obs.complete();
        },
      });
    });
  }

  logout(): void {
    this.currentUser$.next(null);
    this.clearStoredAuth();
    this.router.navigate(['/']);
  }

  setHasResume(hasResume: boolean): void {
    const u = this.currentUser$.value;
    if (u) {
      const updated = { ...u, hasResume };
      this.currentUser$.next(updated);
      sessionStorage.setItem(USER_KEY, JSON.stringify(updated));
    }
  }

  updateProfile(payload: ProfileUpdateRequest): Observable<{ success: boolean; error?: string }> {
    return new Observable((obs) => {
      this.authApi.updateProfile(payload).subscribe({
        next: (res: UserResponse) => {
          const user: User = {
            id: res.id,
            email: res.email,
            name: res.email.split('@')[0],
            hasResume: res.has_resume,
            isAdmin: res.is_admin ?? false,
            requiresPasswordChange: res.requires_password_change ?? false,
          };
          this.currentUser$.next(user);
          sessionStorage.setItem(USER_KEY, JSON.stringify(user));
          obs.next({ success: true });
          obs.complete();
        },
        error: (err) => {
          const d = err.error?.detail;
          const msg = Array.isArray(d) ? (d[0]?.msg ?? d) : (d ?? err.message ?? 'Update failed');
          obs.next({ success: false, error: msg });
          obs.complete();
        },
      });
    });
  }

  deleteAccount(): Observable<{ success: boolean; error?: string }> {
    return new Observable((obs) => {
      this.authApi.deleteAccount().subscribe({
        next: () => {
          this.logout();
          obs.next({ success: true });
          obs.complete();
        },
        error: (err) => {
          obs.next({
            success: false,
            error: err.error?.detail || err.message || 'Delete failed',
          });
          obs.complete();
        },
      });
    });
  }

  getAuthHeaders(): HttpHeaders {
    const t = this.token;
    return new HttpHeaders(t ? { Authorization: `Bearer ${t}` } : {});
  }
}
