import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { TailorResumeRoutingModule } from './tailor-resume-routing.module';
import { TailorResumePageComponent } from './tailor-resume-page/tailor-resume-page.component';

@NgModule({
  declarations: [TailorResumePageComponent],
  imports: [
    CommonModule,
    FormsModule,
    TailorResumeRoutingModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
})
export class TailorResumeModule {}
