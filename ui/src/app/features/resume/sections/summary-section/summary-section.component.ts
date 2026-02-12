import { Component, Input, Output, EventEmitter } from '@angular/core';
import { sectionEnter } from '../../../../animations';

@Component({
  selector: 'app-summary-section',
  templateUrl: './summary-section.component.html',
  styleUrls: ['./summary-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter],
})
export class SummarySectionComponent {
  @Input() summary: string | null = null;
  @Output() summaryChange = new EventEmitter<string | null>();

  get value(): string {
    return this.summary ?? '';
  }

  set value(v: string) {
    this.summaryChange.emit(v || null);
  }
}
