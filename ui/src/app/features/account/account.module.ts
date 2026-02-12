import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDialogModule } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';

import { AccountPageComponent } from './account-page/account-page.component';
import { ConfirmDeleteAccountDialogComponent } from './confirm-delete-account-dialog/confirm-delete-account-dialog.component';
import { AccountRoutingModule } from './account-routing.module';

@NgModule({
  declarations: [AccountPageComponent, ConfirmDeleteAccountDialogComponent],
  imports: [
    CommonModule,
    FormsModule,
    AccountRoutingModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatDialogModule,
    MatProgressSpinnerModule,
    MatIconModule,
  ],
})
export class AccountModule {}
