import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthApiService } from '../../../core/services/auth-api.service';

@Component({
  selector: 'app-forgot-password',
  templateUrl: './forgot-password.component.html',
  styleUrls: ['./forgot-password.component.scss'],
})
export class ForgotPasswordComponent {
  email = '';
  loading = false;
  error = '';
  success = false;
  tempPassword = '';
  expiresIn = 0;

  constructor(
    private authApi: AuthApiService,
    private router: Router,
  ) {}

  onSubmit(): void {
    this.error = '';
    if (!this.email?.trim()) {
      this.error = 'Email is required';
      return;
    }
    this.loading = true;
    this.authApi.forgotPassword(this.email.trim()).subscribe({
      next: (res) => {
        this.loading = false;
        this.success = true;
        this.tempPassword = res.temp_password ?? '';
        this.expiresIn = res.expires_in_minutes ?? 10;
      },
      error: (err) => {
        this.loading = false;
        this.error = err.error?.detail || err.message || 'Request failed';
      },
    });
  }

  goToLogin(): void {
    this.router.navigate(['/auth/login']);
  }
}
