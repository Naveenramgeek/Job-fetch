import { Component, Input } from '@angular/core';
import { CustomSection } from '../../../../models/resume.model';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-custom-sections',
  templateUrl: './custom-sections.component.html',
  styleUrls: ['./custom-sections.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class CustomSectionsComponent {
  @Input() customSections!: CustomSection[];

  addSection(): void {
    this.customSections = this.customSections || [];
    this.customSections.push({ title: '', content: '', link: null });
  }

  removeSection(i: number): void {
    this.customSections.splice(i, 1);
  }
}
