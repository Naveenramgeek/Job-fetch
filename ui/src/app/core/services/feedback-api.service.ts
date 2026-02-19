import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SubmitFeedbackRequest {
  category?: string | null;
  message: string;
  rating?: number | null;
  page?: string | null;
}

export interface FeedbackItemResponse {
  id: string;
  category: string | null;
  message: string;
  rating: number | null;
  page: string | null;
  created_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class FeedbackApiService {
  private readonly base = `${environment.apiBaseUrl}/feedback`;

  constructor(private http: HttpClient) {}

  submit(body: SubmitFeedbackRequest): Observable<FeedbackItemResponse> {
    return this.http.post<FeedbackItemResponse>(this.base, body);
  }
}
