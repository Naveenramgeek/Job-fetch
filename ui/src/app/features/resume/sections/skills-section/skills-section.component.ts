import { Component, Input } from '@angular/core';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-skills-section',
  templateUrl: './skills-section.component.html',
  styleUrls: ['./skills-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class SkillsSectionComponent {
  @Input() skills!: Record<string, string[]>;

  get groups(): { key: string; values: string[] }[] {
    return Object.entries(this.skills || {}).map(([key, values]) => ({ key, values: values || [] }));
  }

  trackByKey(_: number, g: { key: string }): string {
    return g.key;
  }

  addGroup(): void {
    const label = 'New category';
    if (!this.skills[label]) {
      this.skills[label] = [];
    }
  }

  renameGroup(oldKey: string, newKey: string): void {
    if (!newKey || newKey === oldKey) return;
    this.skills[newKey] = this.skills[oldKey] ?? [];
    delete this.skills[oldKey];
  }

  removeGroup(key: string): void {
    delete this.skills[key];
  }

  addSkill(values: string[]): void {
    values.push('');
  }

  removeSkill(values: string[], i: number): void {
    values.splice(i, 1);
  }
}
