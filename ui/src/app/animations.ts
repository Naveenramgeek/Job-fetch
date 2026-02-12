import {
  trigger,
  transition,
  style,
  animate,
} from '@angular/animations';

export const pageEnter = trigger('pageEnter', [
  transition(':enter', [
    style({ opacity: 0 }),
    animate('400ms ease-out', style({ opacity: 1 })),
  ]),
]);

export const editEnter = trigger('editEnter', [
  transition(':enter', [
    style({ opacity: 0, transform: 'translateY(8px)' }),
    animate('350ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
  ]),
]);

export const cardEnter = trigger('cardEnter', [
  transition(':enter', [
    style({ opacity: 0, transform: 'scale(0.98)' }),
    animate('400ms ease-out', style({ opacity: 1, transform: 'scale(1)' })),
  ]),
]);

export const fadeIn = trigger('fadeIn', [
  transition(':enter', [
    style({ opacity: 0 }),
    animate('250ms ease-out', style({ opacity: 1 })),
  ]),
]);

export const sectionEnter = trigger('sectionEnter', [
  transition(':enter', [
    style({ opacity: 0, transform: 'translateY(12px)' }),
    animate('300ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
  ]),
]);

export const itemEnter = trigger('itemEnter', [
  transition(':enter', [
    style({ opacity: 0, transform: 'translateX(-8px)' }),
    animate('250ms ease-out', style({ opacity: 1, transform: 'translateX(0)' })),
  ]),
]);

export const heroEnter = trigger('heroEnter', [
  transition(':enter', [
    style({ opacity: 0, transform: 'translateY(24px)' }),
    animate('600ms 100ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
  ]),
]);

export const floatEnter = trigger('floatEnter', [
  transition(':enter', [
    style({ opacity: 0, transform: 'scale(0.9)' }),
    animate('500ms ease-out', style({ opacity: 1, transform: 'scale(1)' })),
  ]),
]);
