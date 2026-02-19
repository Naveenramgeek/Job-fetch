import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface RegisterRequest {
  email: string;
  password: string;
  confirm_password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserResponse {
  id: string;
  email: string;
  has_resume: boolean;
  is_admin?: boolean;
  requires_password_change?: boolean;
}

export interface ForgotPasswordResponse {
  message: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface RegisterMessageResponse {
  message: string;
}

@Injectable({ providedIn: 'root' })
export class AuthApiService {
  private readonly base = `${environment.apiBaseUrl}/auth`;

  constructor(private http: HttpClient) {}

  register(data: RegisterRequest): Observable<AuthResponse | RegisterMessageResponse> {
    return this.http.post<AuthResponse | RegisterMessageResponse>(`${this.base}/register`, data);
  }

  login(data: LoginRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.base}/login`, data);
  }

  getProfile(): Observable<UserResponse> {
    return this.http.get<UserResponse>(`${this.base}/me`);
  }

  updateProfile(payload: ProfileUpdateRequest): Observable<UserResponse> {
    return this.http.patch<UserResponse>(`${this.base}/me`, payload);
  }

  deleteAccount(): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.base}/account`);
  }

  forgotPassword(email: string): Observable<ForgotPasswordResponse> {
    return this.http.post<ForgotPasswordResponse>(`${this.base}/forgot-password`, { email });
  }

  resetPassword(token: string, newPassword: string, confirmPassword: string): Observable<RegisterMessageResponse> {
    return this.http.post<RegisterMessageResponse>(`${this.base}/reset-password`, {
      token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  }

  changePassword(newPassword: string, confirmPassword: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.base}/change-password`, {
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  }

  activateAccount(token: string): Observable<AuthResponse> {
    return this.http.get<AuthResponse>(`${this.base}/activate?token=${encodeURIComponent(token)}`);
  }

  resendActivation(email: string): Observable<RegisterMessageResponse> {
    return this.http.post<RegisterMessageResponse>(`${this.base}/resend-activation`, { email });
  }
}

export interface ProfileUpdateRequest {
  email?: string;
  current_password?: string;
  new_password?: string;
  confirm_new_password?: string;
}
