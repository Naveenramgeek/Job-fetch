import { Component, Input } from '@angular/core';
import { EducationItem } from '../../../../models/resume.model';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-education-section',
  templateUrl: './education-section.component.html',
  styleUrls: ['./education-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class EducationSectionComponent {
  @Input() education!: EducationItem[];

  addItem(): void {
    this.education.push({
      degree: null,
      institution: null,
      location: null,
      duration: null,
      start: null,
      end: null,
      graduation: null,
      gpa: null,
    });
  }

  removeItem(i: number): void {
    this.education.splice(i, 1);
  }
}
