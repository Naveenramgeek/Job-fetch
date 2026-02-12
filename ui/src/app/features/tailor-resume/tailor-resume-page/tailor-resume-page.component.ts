import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
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
  selector: 'app-tailor-resume-page',
  templateUrl: './tailor-resume-page.component.html',
  styleUrls: ['./tailor-resume-page.component.scss'],
})
export class TailorResumePageComponent implements AfterViewInit, OnDestroy {
  @ViewChild('latexEditor', { static: true }) latexEditorRef!: ElementRef<HTMLDivElement>;

  jobTitle = '';
  jdText = '';
  showJdForm = true;
  loading = false;
  renderLoading = false;
  latex = '';
  alertVisible = false;
  alertType: AlertType = 'success';
  alertMessage = '';
  pdfPreviewUrl: SafeResourceUrl | null = null;
  private pdfObjectUrl: string | null = null;
  private editorView: EditorView | null = null;
  private syncingEditor = false;
  private alertTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private jobsService: JobsService,
    private sanitizer: DomSanitizer,
  ) {}

  ngAfterViewInit(): void {
    this.initEditor();
  }

  ngOnDestroy(): void {
    this.clearAlertTimer();
    this.cleanupPdfObjectUrl();
    this.editorView?.destroy();
    this.editorView = null;
  }

  tailorFromJd(): void {
    const jd = this.jdText?.trim();
    if (!jd) {
      this.showAlert('warning', 'Please add job description text.');
      return;
    }
    this.loading = true;
    this.closeAlert();
    this.cleanupPdfObjectUrl();
    this.pdfPreviewUrl = null;
    this.jobsService.tailorResumeFromJd(jd, this.jobTitle || undefined).subscribe({
      next: (res) => {
        this.loading = false;
        this.latex = res.latex || '';
        this.showJdForm = false;
        this.setEditorDocument(this.latex);
        this.showAlert('success', 'Tailored resume generated.');
        this.renderPdf();
      },
      error: (err) => {
        this.loading = false;
        this.showAlert('error', err?.error?.detail || 'Failed to tailor resume from job description.');
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
    a.download = 'tailored_resume_from_jd.tex';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  showInputs(): void {
    this.showJdForm = true;
  }

  closeAlert(): void {
    this.clearAlertTimer();
    this.alertVisible = false;
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

  private cleanupPdfObjectUrl(): void {
    if (this.pdfObjectUrl) {
      URL.revokeObjectURL(this.pdfObjectUrl);
      this.pdfObjectUrl = null;
    }
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
