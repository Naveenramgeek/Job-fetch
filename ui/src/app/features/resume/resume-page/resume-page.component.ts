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
import { Contact, CustomSection, StructuredResume } from '../../../models/resume.model';
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
    return data;
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
