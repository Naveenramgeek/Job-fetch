import { Component } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
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
  banner = '';

  constructor(
    private auth: AuthService,
    private route: ActivatedRoute,
    private router: Router,
  ) {
    const activationRequired = this.route.snapshot.queryParamMap.get('activation_required');
    if (activationRequired === '1') {
      this.banner = 'Account created. Please activate your account from the email link, then come back and sign in.';
    }
  }

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
