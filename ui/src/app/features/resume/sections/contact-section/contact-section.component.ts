import { Component, Input } from '@angular/core';
import { Contact } from '../../../../models/resume.model';
import { sectionEnter } from '../../../../animations';

@Component({
  selector: 'app-contact-section',
  templateUrl: './contact-section.component.html',
  styleUrls: ['./contact-section.component.scss', '../section-common.scss'],
  animations: [sectionEnter],
})
export class ContactSectionComponent {
  @Input() contact!: Contact;
}
