import { Component, Input } from '@angular/core';
import { ProjectItem } from '../../../../models/resume.model';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-projects-section',
  templateUrl: './projects-section.component.html',
  styleUrls: ['./projects-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class ProjectsSectionComponent {
  @Input() projects!: ProjectItem[];

  addItem(): void {
    this.projects.push({ name: null, bullets: [], link: null });
  }

  removeItem(i: number): void {
    this.projects.splice(i, 1);
  }

  addBullet(project: ProjectItem): void {
    project.bullets = project.bullets || [];
    project.bullets.push('');
  }

  removeBullet(project: ProjectItem, bi: number): void {
    project.bullets.splice(bi, 1);
  }
}
