import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { DashboardPageComponent } from './dashboard-page/dashboard-page.component';
import { ApplicationStatusDialogComponent } from './application-status-dialog/application-status-dialog.component';
import { ResumeTailorPageComponent } from './resume-tailor-page/resume-tailor-page.component';
import { DashboardRoutingModule } from './dashboard-routing.module';

@NgModule({
  declarations: [DashboardPageComponent, ApplicationStatusDialogComponent, ResumeTailorPageComponent],
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    DashboardRoutingModule,
    MatButtonModule,
    MatIconModule,
    MatDialogModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
  ],
})
export class DashboardModule {}
