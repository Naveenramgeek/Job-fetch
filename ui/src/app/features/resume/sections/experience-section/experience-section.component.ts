import { Component, Input } from '@angular/core';
import { ExperienceItem } from '../../../../models/resume.model';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-experience-section',
  templateUrl: './experience-section.component.html',
  styleUrls: ['./experience-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class ExperienceSectionComponent {
  @Input() experience!: ExperienceItem[];

  addItem(): void {
    this.experience.push({
      title: null,
      company: null,
      location: null,
      duration: null,
      start: null,
      end: null,
      bullets: [],
    });
  }

  removeItem(i: number): void {
    this.experience.splice(i, 1);
  }

  addBullet(item: ExperienceItem): void {
    item.bullets = item.bullets || [];
    item.bullets.push('');
  }

  removeBullet(item: ExperienceItem, bi: number): void {
    item.bullets.splice(bi, 1);
  }
}
