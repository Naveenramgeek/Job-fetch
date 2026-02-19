import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthApiService } from '../../../core/services/auth-api.service';

@Component({
  selector: 'app-reset-password',
  templateUrl: './reset-password.component.html',
  styleUrls: ['./reset-password.component.scss'],
})
export class ResetPasswordComponent implements OnInit {
  token = '';
  newPassword = '';
  confirmPassword = '';
  loading = false;
  error = '';
  success = '';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private authApi: AuthApiService,
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
    if (!this.token) {
      this.error = 'Reset link is invalid or missing token.';
    }
  }

  onSubmit(): void {
    this.error = '';
    this.success = '';
    if (!this.token) {
      this.error = 'Reset link is invalid or missing token.';
      return;
    }
    if (!this.newPassword || this.newPassword.length < 8) {
      this.error = 'Password must be at least 8 characters';
      return;
    }
    if (this.newPassword !== this.confirmPassword) {
      this.error = 'Passwords do not match';
      return;
    }

    this.loading = true;
    this.authApi.resetPassword(this.token, this.newPassword, this.confirmPassword).subscribe({
      next: (res) => {
        this.loading = false;
        this.success = res.message || 'Password updated successfully.';
        setTimeout(() => this.router.navigate(['/auth/login']), 800);
      },
      error: (err) => {
        this.loading = false;
        this.error = err.error?.detail || err.message || 'Failed to reset password';
      },
    });
  }
}
