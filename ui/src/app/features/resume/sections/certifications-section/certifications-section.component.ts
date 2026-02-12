import { Component, Input } from '@angular/core';
import { CertificationItem } from '../../../../models/resume.model';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-certifications-section',
  templateUrl: './certifications-section.component.html',
  styleUrls: ['./certifications-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class CertificationsSectionComponent {
  @Input() certifications!: CertificationItem[];

  addItem(): void {
    this.certifications = this.certifications || [];
    this.certifications.push({ text: '', link: null });
  }

  removeItem(i: number): void {
    this.certifications.splice(i, 1);
  }
}
