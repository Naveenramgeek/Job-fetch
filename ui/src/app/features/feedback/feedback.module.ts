import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { FeedbackRoutingModule } from './feedback-routing.module';
import { FeedbackPageComponent } from './feedback-page/feedback-page.component';

@NgModule({
  declarations: [FeedbackPageComponent],
  imports: [
    CommonModule,
    FormsModule,
    FeedbackRoutingModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
})
export class FeedbackModule {}
