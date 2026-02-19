import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';

export interface UnsavedResumeWarningDialogData {
  message: string;
}

@Component({
  selector: 'app-unsaved-resume-warning-dialog',
  templateUrl: './unsaved-resume-warning-dialog.component.html',
  styleUrls: ['./unsaved-resume-warning-dialog.component.scss'],
})
export class UnsavedResumeWarningDialogComponent {
  constructor(
    private dialogRef: MatDialogRef<UnsavedResumeWarningDialogComponent, 'stay' | 'leave'>,
    @Inject(MAT_DIALOG_DATA) public data: UnsavedResumeWarningDialogData,
  ) {}

  stayOnResume(): void {
    this.dialogRef.close('stay');
  }

  saveLaterAndLeave(): void {
    this.dialogRef.close('leave');
  }
}
