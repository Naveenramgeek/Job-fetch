import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { AuthApiService } from '../../../core/services/auth-api.service';

@Component({
  selector: 'app-change-password',
  templateUrl: './change-password.component.html',
  styleUrls: ['./change-password.component.scss'],
})
export class ChangePasswordComponent {
  newPassword = '';
  confirmPassword = '';
  loading = false;
  error = '';

  constructor(
    public auth: AuthService,
    private authApi: AuthApiService,
    private router: Router,
  ) {}

  onSubmit(): void {
    this.error = '';
    if (!this.newPassword) {
      this.error = 'Password is required';
      return;
    }
    if (this.newPassword.length < 8) {
      this.error = 'Password must be at least 8 characters';
      return;
    }
    if (this.newPassword !== this.confirmPassword) {
      this.error = 'Passwords do not match';
      return;
    }
    this.loading = true;
    this.authApi.changePassword(this.newPassword, this.confirmPassword).subscribe({
      next: (res) => {
        this.auth.setAuthFromResponse(res);
        this.loading = false;
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.loading = false;
        this.error = err.error?.detail || err.message || 'Failed to change password';
      },
    });
  }
}
