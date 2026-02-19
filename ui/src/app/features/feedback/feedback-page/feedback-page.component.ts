import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { FeedbackApiService } from '../../../core/services/feedback-api.service';

@Component({
  selector: 'app-feedback-page',
  templateUrl: './feedback-page.component.html',
  styleUrls: ['./feedback-page.component.scss'],
})
export class FeedbackPageComponent {
  category = 'General';
  rating: number | null = null;
  message = '';
  loading = false;
  error = '';
  success = '';

  readonly categories = ['General', 'UI/UX', 'Performance', 'Bug report', 'Feature request', 'Other'];

  constructor(
    private feedbackApi: FeedbackApiService,
    private router: Router,
  ) {}

  submit(): void {
    this.error = '';
    this.success = '';
    if (!this.message.trim()) {
      this.error = 'Please enter your feedback before submitting.';
      return;
    }
    this.loading = true;
    this.feedbackApi
      .submit({
        category: this.category,
        rating: this.rating,
        message: this.message.trim(),
        page: this.router.url,
      })
      .subscribe({
        next: () => {
          this.loading = false;
          this.success = 'Thanks for your feedback. We use it to improve the app usability.';
          this.message = '';
          this.rating = null;
          this.category = 'General';
        },
        error: (err) => {
          this.loading = false;
          this.error = err?.error?.detail || err?.message || 'Failed to submit feedback.';
        },
      });
  }
}
