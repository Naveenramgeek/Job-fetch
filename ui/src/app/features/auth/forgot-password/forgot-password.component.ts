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
  successMessage = '';

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
        this.successMessage = res.message || 'If an account exists, a password reset link has been sent to email.';
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
