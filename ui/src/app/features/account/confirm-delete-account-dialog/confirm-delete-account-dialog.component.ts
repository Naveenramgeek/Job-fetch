import { Component } from '@angular/core';
import { MatDialogRef } from '@angular/material/dialog';

@Component({
  selector: 'app-confirm-delete-account-dialog',
  templateUrl: './confirm-delete-account-dialog.component.html',
  styleUrls: ['./confirm-delete-account-dialog.component.scss'],
})
export class ConfirmDeleteAccountDialogComponent {
  constructor(public dialogRef: MatDialogRef<ConfirmDeleteAccountDialogComponent>) {}

  confirm(): void {
    this.dialogRef.close(true);
  }

  cancel(): void {
    this.dialogRef.close(false);
  }
}
