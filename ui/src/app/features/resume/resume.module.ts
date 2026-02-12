import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSelectModule } from '@angular/material/select';

import { ResumeRoutingModule } from './resume-routing.module';
import { ResumePageComponent } from './resume-page/resume-page.component';
import { ContactSectionComponent } from './sections/contact-section/contact-section.component';
import { SummarySectionComponent } from './sections/summary-section/summary-section.component';
import { ExperienceSectionComponent } from './sections/experience-section/experience-section.component';
import { EducationSectionComponent } from './sections/education-section/education-section.component';
import { ProjectsSectionComponent } from './sections/projects-section/projects-section.component';
import { SkillsSectionComponent } from './sections/skills-section/skills-section.component';
import { CertificationsSectionComponent } from './sections/certifications-section/certifications-section.component';
import { OtherSectionComponent } from './sections/other-section/other-section.component';
import { CustomSectionsComponent } from './sections/custom-sections/custom-sections.component';

@NgModule({
  declarations: [
    ResumePageComponent,
    ContactSectionComponent,
    SummarySectionComponent,
    ExperienceSectionComponent,
    EducationSectionComponent,
    ProjectsSectionComponent,
    SkillsSectionComponent,
    CertificationsSectionComponent,
    OtherSectionComponent,
    CustomSectionsComponent,
  ],
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    ResumeRoutingModule,
    RouterModule,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatExpansionModule,
    MatTabsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatChipsModule,
    MatDividerModule,
    MatTooltipModule,
    MatSelectModule,
  ],
})
export class ResumeModule {}
