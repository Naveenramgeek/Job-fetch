import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { StructuredResume } from '../../models/resume.model';

@Injectable({ providedIn: 'root' })
export class ResumeApiService {
  private readonly base = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  getResume(): Observable<{ id: string; user_id: string; parsed_data: StructuredResume }> {
    return this.http.get<{ id: string; user_id: string; parsed_data: StructuredResume }>(
      `${this.base}/resumes/latest`
    );
  }

  /** Upload PDF, parse it, and return structured data. Then save via POST /resumes to persist. */
  parsePdf(file: File): Observable<StructuredResume> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<StructuredResume>(`${this.base}/parse`, formData);
  }

  saveResume(parsedData: StructuredResume): Observable<{ id: string; user_id: string; parsed_data: StructuredResume }> {
    return this.http.post<{ id: string; user_id: string; parsed_data: StructuredResume }>(
      `${this.base}/resumes`,
      { parsed_data: parsedData }
    );
  }

  updateResume(parsedData: StructuredResume): Observable<{ id: string; user_id: string; parsed_data: StructuredResume }> {
    return this.http.put<{ id: string; user_id: string; parsed_data: StructuredResume }>(
      `${this.base}/resumes/latest`,
      { parsed_data: parsedData }
    );
  }

  validate(resume: StructuredResume): Observable<StructuredResume> {
    const url = `${this.base}/validate`;
    return this.http.post<StructuredResume>(url, resume);
  }
}
