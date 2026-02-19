import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthApiService } from '../../../core/services/auth-api.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-signup',
  templateUrl: './signup.component.html',
  styleUrls: ['./signup.component.scss'],
})
export class SignupComponent {
  email = '';
  password = '';
  confirmPassword = '';
  loading = false;
  error = '';
  successMessage = '';

  constructor(
    private authApi: AuthApiService,
    private auth: AuthService,
    private router: Router,
  ) {}

  onSubmit(): void {
    this.error = '';
    this.successMessage = '';
    if (!this.email?.trim()) {
      this.error = 'Email is required';
      return;
    }
    if (!this.password) {
      this.error = 'Password is required';
      return;
    }
    if (this.password.length < 8) {
      this.error = 'Password must be at least 8 characters';
      return;
    }
    if (this.password !== this.confirmPassword) {
      this.error = 'Passwords do not match';
      return;
    }
    this.loading = true;
    this.authApi
      .register({
        email: this.email.trim(),
        password: this.password,
        confirm_password: this.confirmPassword,
      })
      .subscribe({
        next: (res) => {
          if ('access_token' in res) {
            this.auth.setAuthFromResponse(res);
            this.router.navigate(['/dashboard']);
            return;
          }
          this.successMessage = res.message || 'Registration successful. Please check your email to activate your account.';
          this.router.navigate(['/auth/login'], { queryParams: { activation_required: '1' } });
        },
        error: (err) => {
          this.error = err.error?.detail || err.message || 'Registration failed';
          if (Array.isArray(this.error)) {
            this.error = this.error.join(', ');
          }
        },
        complete: () => {
          this.loading = false;
        },
      });
  }
}
