import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { JobListing } from '../../../models/job.model';

export interface ApplicationStatusDialogData {
  job: JobListing;
}

@Component({
  selector: 'app-application-status-dialog',
  templateUrl: './application-status-dialog.component.html',
  styleUrls: ['./application-status-dialog.component.scss'],
})
export class ApplicationStatusDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<ApplicationStatusDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: ApplicationStatusDialogData,
  ) {}

  select(status: 'applied' | 'not_applied'): void {
    this.dialogRef.close(status);
  }

  dismiss(): void {
    this.dialogRef.close();
  }
}
