import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { StreamLanguage } from '@codemirror/language';
import { stex } from '@codemirror/legacy-modes/mode/stex';
import { oneDark } from '@codemirror/theme-one-dark';
import { basicSetup } from 'codemirror';

import { JobsService } from '../../../core/services/jobs.service';

type AlertType = 'success' | 'error' | 'warning';

@Component({
  selector: 'app-resume-tailor-page',
  templateUrl: './resume-tailor-page.component.html',
  styleUrls: ['./resume-tailor-page.component.scss'],
})
export class ResumeTailorPageComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('latexEditor', { static: true }) latexEditorRef!: ElementRef<HTMLDivElement>;

  matchId = '';
  title = '';
  company = '';
  latex = '';
  loading = false;
  renderLoading = false;
  alertVisible = false;
  alertType: AlertType = 'success';
  alertMessage = '';
  pdfPreviewUrl: SafeResourceUrl | null = null;
  private pdfObjectUrl: string | null = null;
  private editorView: EditorView | null = null;
  private syncingEditor = false;
  private alertTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private route: ActivatedRoute,
    private jobsService: JobsService,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    this.matchId = this.route.snapshot.paramMap.get('matchId') || '';
    this.title = this.route.snapshot.queryParamMap.get('title') || '';
    this.company = this.route.snapshot.queryParamMap.get('company') || '';
    if (!this.matchId) {
      this.showAlert('error', 'Missing match id.');
      return;
    }
    this.generateTailoredResume();
  }

  ngAfterViewInit(): void {
    this.initEditor();
  }

  ngOnDestroy(): void {
    this.clearAlertTimer();
    this.cleanupPdfObjectUrl();
    this.editorView?.destroy();
    this.editorView = null;
  }

  generateTailoredResume(): void {
    this.loading = true;
    this.closeAlert();
    this.cleanupPdfObjectUrl();
    this.pdfPreviewUrl = null;
    this.jobsService.tailorResume(this.matchId).subscribe({
      next: (res) => {
        this.loading = false;
        this.latex = res.latex || '';
        this.setEditorDocument(this.latex);
        this.title = res.job_title || this.title;
        this.company = res.company || this.company;
        this.showAlert('success', 'Tailored resume generated.');
        this.renderPdf();
      },
      error: (err) => {
        this.loading = false;
        this.showAlert('error', err?.error?.detail || 'Failed to generate tailored resume.');
      },
    });
  }

  renderPdf(): void {
    if (!this.latex?.trim()) {
      this.showAlert('warning', 'No LaTeX content to render.');
      return;
    }
    this.renderLoading = true;
    this.closeAlert();
    this.jobsService.renderLatexPdf(this.latex).subscribe({
      next: (blob) => {
        this.renderLoading = false;
        this.cleanupPdfObjectUrl();
        this.pdfObjectUrl = URL.createObjectURL(blob);
        this.pdfPreviewUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.pdfObjectUrl);
        this.showAlert('success', 'PDF rendered successfully.');
      },
      error: (err) => {
        this.renderLoading = false;
        const blob = err?.error as Blob | undefined;
        if (blob instanceof Blob) {
          blob.text().then((text) => {
            this.showAlert('error', text || 'Failed to render PDF preview.');
          });
        } else {
          this.showAlert('error', err?.error?.detail || 'Failed to render PDF preview.');
        }
      },
    });
  }

  downloadTex(): void {
    if (!this.latex) return;
    const blob = new Blob([this.latex], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.slugify(`${this.title}-${this.company}`)}_tailored_resume.tex`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  private cleanupPdfObjectUrl(): void {
    if (this.pdfObjectUrl) {
      URL.revokeObjectURL(this.pdfObjectUrl);
      this.pdfObjectUrl = null;
    }
  }

  private slugify(value: string): string {
    return (value || 'resume')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 80) || 'resume';
  }

  private initEditor(): void {
    if (this.editorView || !this.latexEditorRef?.nativeElement) return;
    const updateListener = EditorView.updateListener.of((update) => {
      if (!update.docChanged || this.syncingEditor) return;
      this.latex = update.state.doc.toString();
    });

    this.editorView = new EditorView({
      state: EditorState.create({
        doc: this.latex || '',
        extensions: [basicSetup, oneDark, StreamLanguage.define(stex), updateListener],
      }),
      parent: this.latexEditorRef.nativeElement,
    });
  }

  private setEditorDocument(content: string): void {
    if (!this.editorView) return;
    const current = this.editorView.state.doc.toString();
    if (current === content) return;
    this.syncingEditor = true;
    this.editorView.dispatch({
      changes: { from: 0, to: current.length, insert: content },
    });
    this.syncingEditor = false;
  }

  closeAlert(): void {
    this.clearAlertTimer();
    this.alertVisible = false;
  }

  private showAlert(type: AlertType, message: string): void {
    this.clearAlertTimer();
    this.alertType = type;
    this.alertMessage = message;
    this.alertVisible = true;
    this.alertTimer = setTimeout(() => {
      this.alertVisible = false;
      this.alertTimer = null;
    }, 3000);
  }

  private clearAlertTimer(): void {
    if (this.alertTimer) {
      clearTimeout(this.alertTimer);
      this.alertTimer = null;
    }
  }
}
