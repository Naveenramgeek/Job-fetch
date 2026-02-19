import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { AuthApiService } from '../../../core/services/auth-api.service';

@Component({
  selector: 'app-activate-account',
  templateUrl: './activate-account.component.html',
  styleUrls: ['./activate-account.component.scss'],
})
export class ActivateAccountComponent implements OnInit {
  loading = true;
  error = '';
  message = '';

  constructor(
    private route: ActivatedRoute,
    private authApi: AuthApiService,
  ) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.loading = false;
      this.error = 'Activation token is missing.';
      return;
    }
    this.authApi.activateAccount(token).subscribe({
      next: () => {
        this.message = 'Account activated successfully. Please sign in to continue.';
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.error = err.error?.detail || err.message || 'Activation failed. Please request a new activation email.';
      },
    });
  }
}
