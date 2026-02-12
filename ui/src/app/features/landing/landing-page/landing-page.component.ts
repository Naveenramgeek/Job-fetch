import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { heroEnter, floatEnter } from '../../../animations';

@Component({
  selector: 'app-landing-page',
  templateUrl: './landing-page.component.html',
  styleUrls: ['./landing-page.component.scss'],
  animations: [heroEnter, floatEnter],
})
export class LandingPageComponent {
  features = [
    {
      icon: 'auto_awesome',
      title: 'AI Job Matching',
      desc: 'LLM-powered scoring finds jobs that truly match your resume. No more sifting through hundreds of irrelevant listings.',
    },
    {
      icon: 'description',
      title: 'Smart Resume Parsing',
      desc: 'Build your resume in the app. We use your skills, experience, and education to match you with jobs.',
    },
    {
      icon: 'track_changes',
      title: 'Track Applications',
      desc: 'Mark jobs as applied or skip. Keep your pipeline organized and never lose track of where you applied.',
    },
    {
      icon: 'bolt',
      title: 'Fresh Jobs Daily',
      desc: 'Jobs scraped from LinkedIn, Indeed, Google, and more. See the latest postings that fit your profile.',
    },
    {
      icon: 'auto_fix_high',
      title: 'Resume Tailoring',
      desc: 'Tailor your saved resume to a specific job description with an in-app LaTeX editor and live PDF preview.',
    },
  ];

  constructor(private router: Router) {}

  goToLogin(): void {
    this.router.navigate(['/auth/login']);
  }

  goToSignup(): void {
    this.router.navigate(['/auth/signup']);
  }
}
