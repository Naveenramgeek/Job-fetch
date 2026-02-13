import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { StreamLanguage } from '@codemirror/language';
import { stex } from '@codemirror/legacy-modes/mode/stex';
import { oneDark } from '@codemirror/theme-one-dark';
import { basicSetup } from 'codemirror';
import { ResumeApiService } from '../../../core/services/resume-api.service';
import { JobsService } from '../../../core/services/jobs.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  CertificationItem,
  Contact,
  CustomSection,
  EducationItem,
  ExperienceItem,
  OtherBlock,
  ProjectItem,
  StructuredResume,
} from '../../../models/resume.model';
import { MatSnackBar } from '@angular/material/snack-bar';
import { pageEnter, editEnter } from '../../../animations';

@Component({
  selector: 'app-resume-page',
  templateUrl: './resume-page.component.html',
  styleUrls: ['./resume-page.component.scss'],
  animations: [pageEnter, editEnter],
})
export class ResumePageComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('resumeTailorEditor') resumeTailorEditorRef?: ElementRef<HTMLDivElement>;

  resume: StructuredResume | null = null;
  loading = false;
  saving = false;
  uploadError: string | null = null;
  activeTabIndex = 0;
  tailorJobTitle = '';
  tailorJdText = '';
  tailorLoading = false;
  tailorRenderLoading = false;
  tailorLatex = '';
  tailorError = '';
  tailorPdfPreviewUrl: SafeResourceUrl | null = null;
  private tailorPdfObjectUrl: string | null = null;
  private tailorEditorView: EditorView | null = null;
  private syncingTailorEditor = false;

  constructor(
    private api: ResumeApiService,
    private jobsService: JobsService,
    public auth: AuthService,
    private snackBar: MatSnackBar,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    if (this.auth.currentUserValue?.hasResume) {
      this.loadSavedResume();
    }
  }

  ngAfterViewInit(): void {
    if (this.activeTabIndex === 9) {
      setTimeout(() => this.initTailorEditor(), 0);
    }
  }

  ngOnDestroy(): void {
    this.cleanupTailorPdfObjectUrl();
    this.tailorEditorView?.destroy();
    this.tailorEditorView = null;
  }

  loadSavedResume(): void {
    this.loading = true;
    this.uploadError = null;
    this.api.getResume().subscribe({
      next: (res) => {
        this.resume = this.normalizeResume(res.parsed_data);
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        if (err.status === 404) {
          this.auth.setHasResume(false);
        } else {
          this.uploadError = err.error?.detail || 'Failed to load saved resume.';
        }
      },
    });
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input?.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.uploadError = 'Please select a PDF file.';
      this.snackBar.open('Please select a PDF file.', 'Close', { duration: 3000 });
      input.value = '';
      return;
    }
    this.loading = true;
    this.uploadError = null;
    this.api.parsePdf(file).subscribe({
      next: (parsed) => {
        this.resume = this.normalizeResume(parsed);
        this.activeTabIndex = 0;
        this.loading = false;
        this.auth.setHasResume(true);
        this.snackBar.open('PDF parsed. Review and save your resume.', 'Close', { duration: 4000 });
        input.value = '';
      },
      error: (err) => {
        this.loading = false;
        this.uploadError = err.error?.detail || err.message || 'Failed to parse PDF.';
        this.snackBar.open(this.uploadError ?? 'Failed to parse PDF.', 'Close', { duration: 5000 });
        input.value = '';
      },
    });
  }

  private normalizeResume(data: StructuredResume): StructuredResume {
    if (!Array.isArray((data as any).custom_sections)) {
      (data as any).custom_sections = [];
    }
    if (!Array.isArray((data as any).experience)) (data as any).experience = [];
    if (!Array.isArray((data as any).education)) (data as any).education = [];
    if (!Array.isArray((data as any).projects)) (data as any).projects = [];
    if (!Array.isArray((data as any).certifications)) (data as any).certifications = [];
    if (!Array.isArray((data as any).other)) (data as any).other = [];
    if (!data.skills || typeof data.skills !== 'object') (data as any).skills = {};
    if (data.contact) {
      const c = data.contact as Contact;
      if (c.title === undefined) c.title = null;
    }
    // Backward compat: certifications may be string[] from older saves
    if (Array.isArray(data.certifications) && data.certifications.length > 0) {
      const first = data.certifications[0];
      if (typeof first === 'string') {
        (data as any).certifications = (data.certifications as unknown as string[]).map((s) => ({ text: s, link: null }));
      }
    }
    this.promoteParseFailedSections(data);
    return data;
  }

  private promoteParseFailedSections(data: StructuredResume): void {
    const otherBlocks = Array.isArray(data.other) ? data.other : [];
    const remaining: OtherBlock[] = [];

    for (const block of otherBlocks) {
      const source = block?.source_section;
      const reason = block?.reason || '';
      const text = (block?.text || '').trim();
      const parseFailed = reason.endsWith('_parse_failed');

      if (!parseFailed || !source || !text) {
        remaining.push(block);
        continue;
      }

      let promoted = false;
      if (source === 'experience' && data.experience.length === 0) {
        const experience = this.parseFallbackExperience(text);
        if (experience.length) {
          data.experience = experience;
          promoted = true;
        }
      } else if (source === 'education' && data.education.length === 0) {
        const education = this.parseFallbackEducation(text);
        if (education.length) {
          data.education = education;
          promoted = true;
        }
      } else if (source === 'projects' && data.projects.length === 0) {
        const projects = this.parseFallbackProjects(text);
        if (projects.length) {
          data.projects = projects;
          promoted = true;
        }
      } else if (source === 'skills' && Object.keys(data.skills || {}).length === 0) {
        const skills = this.parseFallbackSkills(text);
        if (Object.keys(skills).length) {
          data.skills = skills;
          promoted = true;
        }
      } else if (source === 'certifications' && data.certifications.length === 0) {
        const certifications = this.parseFallbackCertifications(text);
        if (certifications.length) {
          data.certifications = certifications;
          promoted = true;
        }
      }

      if (!promoted) {
        remaining.push(block);
      }
    }

    data.other = remaining;
  }

  private parseFallbackExperience(text: string): ExperienceItem[] {
    const lines = this.lines(text);
    const out: ExperienceItem[] = [];
    let current: ExperienceItem | null = null;

    for (const line of lines) {
      if (this.isBullet(line)) {
        if (!current) current = this.emptyExperience(null);
        current.bullets.push(this.stripBullet(line));
        continue;
      }

      if (!current) {
        current = this.emptyExperience(line);
        continue;
      }

      if (this.looksLikeExperienceHeader(line)) {
        out.push(current);
        current = this.emptyExperience(line);
      } else {
        current.bullets.push(line);
      }
    }

    if (current) out.push(current);
    return out.filter((x) => !!x.title || x.bullets.length > 0);
  }

  private parseFallbackEducation(text: string): EducationItem[] {
    const lines = this.lines(text).map((line) => this.stripBullet(line));
    const out: EducationItem[] = [];
    for (const line of lines) {
      out.push({
        degree: line || null,
        institution: null,
        location: null,
        duration: null,
        start: null,
        end: null,
        graduation: null,
        gpa: null,
      });
    }
    return out;
  }

  private parseFallbackProjects(text: string): ProjectItem[] {
    const lines = this.lines(text);
    if (!lines.length) return [];

    const out: ProjectItem[] = [];
    let current: ProjectItem = { name: this.stripBullet(lines[0]) || null, bullets: [], link: null };

    for (const line of lines.slice(1)) {
      if (this.isBullet(line)) {
        current.bullets.push(this.stripBullet(line));
        continue;
      }
      if (current.name && current.bullets.length > 0) {
        out.push(current);
        current = { name: line, bullets: [], link: null };
      } else {
        current.bullets.push(line);
      }
    }
    out.push(current);
    return out.filter((x) => !!x.name || x.bullets.length > 0);
  }

  private parseFallbackSkills(text: string): Record<string, string[]> {
    const groups: Record<string, string[]> = {};
    const lines = this.lines(text);

    for (const line of lines) {
      if (line.includes(':')) {
        const [rawKey, rawValues] = line.split(':', 2);
        const key = rawKey.trim() || 'Skills';
        const vals = rawValues
          .split(',')
          .map((v) => v.trim())
          .filter(Boolean);
        if (vals.length) groups[key] = vals;
        continue;
      }
      const vals = line
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean);
      if (vals.length) {
        groups.Skills = [...(groups.Skills || []), ...vals];
      }
    }

    return groups;
  }

  private parseFallbackCertifications(text: string): CertificationItem[] {
    return this.lines(text)
      .map((line) => this.stripBullet(line))
      .filter(Boolean)
      .map((line) => ({ text: line, link: null }));
  }

  private emptyExperience(title: string | null): ExperienceItem {
    return {
      title: title || null,
      company: null,
      location: null,
      duration: null,
      start: null,
      end: null,
      bullets: [],
    };
  }

  private lines(text: string): string[] {
    return text
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
  }

  private isBullet(line: string): boolean {
    return /^[-*•]/.test(line.trim());
  }

  private stripBullet(line: string): string {
    return line.replace(/^[-*•]\s*/, '').trim();
  }

  private looksLikeExperienceHeader(line: string): boolean {
    const s = line.trim();
    if (!s || this.isBullet(s)) return false;
    if (/[—-]/.test(s) && /\b(19|20)\d{2}\b/.test(s)) return true;
    if (/\b(present|current)\b/i.test(s) && s.split(/\s+/).length >= 3) return true;
    return false;
  }

  startNewResume(): void {
    this.uploadError = null;
    this.resume = this.getEmptyResume();
    this.activeTabIndex = 0;
  }

  private getEmptyResume(): StructuredResume {
    return {
      contact: {
        name: null,
        title: null,
        email: null,
        phone: null,
        linkedin: null,
        github: null,
        location: null,
      },
      summary: null,
      experience: [],
      projects: [],
      education: [],
      skills: {},
      certifications: [],
      other: [],
      custom_sections: [],
    };
  }

  exportJson(): void {
    if (!this.resume) return;
    const blob = new Blob([JSON.stringify(this.resume, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'resume-structured.json';
    a.click();
    URL.revokeObjectURL(a.href);
    this.snackBar.open('JSON downloaded.', 'Close', { duration: 2000 });
  }

  copyJson(): void {
    if (!this.resume) return;
    navigator.clipboard.writeText(JSON.stringify(this.resume, null, 2)).then(() => {
      this.snackBar.open('JSON copied to clipboard.', 'Close', { duration: 2000 });
    }).catch(() => {
      this.snackBar.open('Copy failed.', 'Close', { duration: 2000 });
    });
  }

  saveResume(): void {
    if (!this.resume) return;
    const validationError = this.validateRequiredFields(this.resume);
    if (validationError) {
      this.snackBar.open(validationError, 'Close', { duration: 5000 });
      return;
    }
    this.saving = true;
    const onSuccess = () => {
      this.saving = false;
      this.auth.setHasResume(true);
      this.snackBar.open('Resume saved.', 'Close', { duration: 3000 });
    };
    const onError = (err: { status?: number; error?: { detail?: string } }) => {
      this.saving = false;
      this.snackBar.open(err.error?.detail || 'Failed to save.', 'Close', { duration: 4000 });
    };
    // Try update first; if 404 (no resume yet), create instead
    this.api.updateResume(this.resume).subscribe({
      next: onSuccess,
      error: (err) => {
        if (err.status === 404) {
          this.api.saveResume(this.resume!).subscribe({ next: onSuccess, error: onError });
        } else {
          onError(err);
        }
      },
    });
  }

  private validateRequiredFields(resume: StructuredResume): string | null {
    const missingContact: string[] = [];
    if (!resume.contact?.name?.trim()) missingContact.push('Name');
    if (!resume.contact?.title?.trim()) missingContact.push('Professional title');
    if (!resume.contact?.email?.trim()) missingContact.push('Email');
    if (missingContact.length) {
      this.activeTabIndex = 0;
      return `Contact required: ${missingContact.join(', ')}`;
    }

    if (!Array.isArray(resume.education) || resume.education.length === 0) {
      this.activeTabIndex = 3;
      return 'Education required: add at least one education entry.';
    }

    for (let i = 0; i < resume.education.length; i++) {
      const e = resume.education[i];
      const missingEdu: string[] = [];
      if (!e.degree?.trim()) missingEdu.push('Degree');
      if (!e.institution?.trim()) missingEdu.push('Institution');
      if (!e.start?.trim()) missingEdu.push('Start');
      if (!e.end?.trim()) missingEdu.push('End');
      if (missingEdu.length) {
        this.activeTabIndex = 3;
        return `Education #${i + 1} required: ${missingEdu.join(', ')}`;
      }
    }
    return null;
  }

  onTabChange(index: number): void {
    this.activeTabIndex = index;
    if (index === 9) {
      setTimeout(() => this.initTailorEditor(), 0);
    }
  }

  generateTailorFromJd(): void {
    const jd = this.tailorJdText?.trim();
    if (!jd) {
      this.tailorError = 'Please add job description text.';
      return;
    }
    this.tailorLoading = true;
    this.tailorError = '';
    this.cleanupTailorPdfObjectUrl();
    this.tailorPdfPreviewUrl = null;
    this.jobsService.tailorResumeFromJd(jd, this.tailorJobTitle || undefined).subscribe({
      next: (res) => {
        this.tailorLoading = false;
        this.tailorLatex = res.latex || '';
        this.setTailorEditorDocument(this.tailorLatex);
        this.renderTailorPdf();
      },
      error: (err) => {
        this.tailorLoading = false;
        this.tailorError = err?.error?.detail || 'Failed to tailor resume from job description.';
      },
    });
  }

  renderTailorPdf(): void {
    if (!this.tailorLatex?.trim()) {
      this.tailorError = 'No LaTeX content to render.';
      return;
    }
    this.tailorRenderLoading = true;
    this.tailorError = '';
    this.jobsService.renderLatexPdf(this.tailorLatex).subscribe({
      next: (blob) => {
        this.tailorRenderLoading = false;
        this.cleanupTailorPdfObjectUrl();
        this.tailorPdfObjectUrl = URL.createObjectURL(blob);
        this.tailorPdfPreviewUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.tailorPdfObjectUrl);
      },
      error: (err) => {
        this.tailorRenderLoading = false;
        const blob = err?.error as Blob | undefined;
        if (blob instanceof Blob) {
          blob.text().then((text) => {
            this.tailorError = text || 'Failed to render PDF preview.';
          });
        } else {
          this.tailorError = err?.error?.detail || 'Failed to render PDF preview.';
        }
      },
    });
  }

  downloadTailorTex(): void {
    if (!this.tailorLatex) return;
    const blob = new Blob([this.tailorLatex], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tailored_resume_from_jd.tex';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  reset(): void {
    this.resume = null;
    this.uploadError = null;
    this.activeTabIndex = 0;
    this.tailorJdText = '';
    this.tailorJobTitle = '';
    this.tailorLatex = '';
    this.tailorError = '';
    this.cleanupTailorPdfObjectUrl();
    this.tailorPdfPreviewUrl = null;
  }

  getCustomSections(): CustomSection[] {
    if (!this.resume) return [];
    if (!Array.isArray(this.resume.custom_sections)) {
      this.resume.custom_sections = [];
    }
    return this.resume.custom_sections;
  }

  private initTailorEditor(): void {
    if (this.tailorEditorView || !this.resumeTailorEditorRef?.nativeElement) return;
    const updateListener = EditorView.updateListener.of((update) => {
      if (!update.docChanged || this.syncingTailorEditor) return;
      this.tailorLatex = update.state.doc.toString();
    });
    this.tailorEditorView = new EditorView({
      state: EditorState.create({
        doc: this.tailorLatex || '',
        extensions: [basicSetup, oneDark, StreamLanguage.define(stex), updateListener],
      }),
      parent: this.resumeTailorEditorRef.nativeElement,
    });
  }

  private setTailorEditorDocument(content: string): void {
    if (!this.tailorEditorView) {
      this.initTailorEditor();
      if (!this.tailorEditorView) return;
    }
    const current = this.tailorEditorView.state.doc.toString();
    if (current === content) return;
    this.syncingTailorEditor = true;
    this.tailorEditorView.dispatch({
      changes: { from: 0, to: current.length, insert: content },
    });
    this.syncingTailorEditor = false;
  }

  private cleanupTailorPdfObjectUrl(): void {
    if (this.tailorPdfObjectUrl) {
      URL.revokeObjectURL(this.tailorPdfObjectUrl);
      this.tailorPdfObjectUrl = null;
    }
  }

}
