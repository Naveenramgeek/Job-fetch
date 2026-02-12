import { Component, Input } from '@angular/core';
import { OtherBlock } from '../../../../models/resume.model';
import { sectionEnter, itemEnter } from '../../../../animations';

@Component({
  selector: 'app-other-section',
  templateUrl: './other-section.component.html',
  styleUrls: ['./other-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter, itemEnter],
})
export class OtherSectionComponent {
  @Input() other!: OtherBlock[];

  trackByIndex(index: number, _item: OtherBlock): number {
    return index;
  }

  removeBlock(i: number): void {
    this.other.splice(i, 1);
  }
}
