import { Component } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { AuthService } from '../../../core/services/auth.service';
import { ConfirmDeleteAccountDialogComponent } from '../confirm-delete-account-dialog/confirm-delete-account-dialog.component';

@Component({
  selector: 'app-account-page',
  templateUrl: './account-page.component.html',
  styleUrls: ['./account-page.component.scss'],
})
export class AccountPageComponent {
  email = '';
  currentPassword = '';
  newPassword = '';
  confirmNewPassword = '';
  loading = false;
  error = '';
  success = '';

  constructor(
    public auth: AuthService,
    private dialog: MatDialog,
  ) {
    const u = this.auth.currentUserValue;
    if (u) this.email = u.email;
  }

  get hasPasswordFields(): boolean {
    return !!(this.newPassword?.trim() || this.confirmNewPassword?.trim());
  }

  onSave(): void {
    this.error = '';
    this.success = '';
    const payload: {
      email?: string;
      current_password?: string;
      new_password?: string;
      confirm_new_password?: string;
    } = {};
    const currentEmail = this.auth.currentUserValue?.email ?? '';
    if (this.email?.trim() && this.email.trim() !== currentEmail) {
      payload.email = this.email.trim();
    }
    if (this.newPassword?.trim()) {
      payload.current_password = this.currentPassword;
      payload.new_password = this.newPassword.trim();
      payload.confirm_new_password = this.confirmNewPassword?.trim() ?? '';
    }
    if (!payload.email && !payload.new_password) {
      this.error = 'Change email or password to save.';
      return;
    }
    if (payload.new_password && payload.new_password !== payload.confirm_new_password) {
      this.error = 'New password and confirmation do not match.';
      return;
    }
    if (payload.new_password && payload.new_password.length < 8) {
      this.error = 'New password must be at least 8 characters.';
      return;
    }
    this.loading = true;
    this.auth.updateProfile(payload).subscribe({
      next: (res: { success: boolean; error?: string }) => {
        this.loading = false;
        if (res.success) {
          this.success = 'Profile updated.';
          this.currentPassword = '';
          this.newPassword = '';
          this.confirmNewPassword = '';
        } else {
          this.error = res.error ?? 'Update failed';
        }
      },
      error: () => {
        this.loading = false;
        this.error = 'Something went wrong.';
      },
    });
  }

  openDeleteDialog(): void {
    const ref = this.dialog.open(ConfirmDeleteAccountDialogComponent, {
      width: '400px',
      disableClose: true,
    });
    ref.afterClosed().subscribe((confirmed: boolean) => {
      if (confirmed) {
        this.error = '';
        this.loading = true;
        this.auth.deleteAccount().subscribe({
          next: (res: { success: boolean; error?: string }) => {
            this.loading = false;
            if (!res.success) this.error = res.error ?? 'Delete failed';
          },
          error: () => {
            this.loading = false;
            this.error = 'Something went wrong.';
          },
        });
      }
    });
  }
}
