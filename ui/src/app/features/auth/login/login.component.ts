import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent {
  email = '';
  password = '';
  loading = false;
  error = '';

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  onSubmit(): void {
    this.error = '';
    if (!this.email?.trim()) {
      this.error = 'Email is required';
      return;
    }
    this.loading = true;
    this.auth.login(this.email.trim(), this.password).subscribe({
      next: (res) => {
        if (res.success) {
          if (this.auth.currentUserValue?.requiresPasswordChange) {
            this.router.navigate(['/auth/change-password']);
          } else {
            this.router.navigate(['/dashboard']);
          }
        } else {
          this.error = res.error || 'Login failed';
        }
      },
      error: () => {
        this.error = 'Something went wrong';
      },
      complete: () => {
        this.loading = false;
      },
    });
  }
}
