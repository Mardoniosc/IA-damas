import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

/** Thin client for the local backend (FastAPI). All calls go through the dev-server proxy at /api. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  health(): Observable<any> {
    return this.http.get(`${this.base}/health`);
  }
  variants(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/variants`);
  }
  engines(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/engines`);
  }
  decision(variant: string, fen: string, moveTime: number, engines?: string[]): Observable<any> {
    return this.http.post(`${this.base}/decision`, {
      variant,
      fen,
      limit: { move_time_s: moveTime },
      engines: engines?.length ? engines : null,
    });
  }
  tactics(variant: string, fen: string, depth: number): Observable<any> {
    return this.http.post(`${this.base}/tactics`, { variant, fen, depth });
  }
  strategy(variant: string, fen: string): Observable<any> {
    return this.http.post(`${this.base}/strategy`, { variant, fen });
  }
  parseGames(pdn: string, variant?: string | null): Observable<any> {
    return this.http.post(`${this.base}/games/parse`, { pdn, variant: variant || null });
  }
  analyzeGame(pdn: string, index: number, engine: string | null, depth: number, variant?: string | null): Observable<any> {
    return this.http.post(`${this.base}/games/analyze`, {
      pdn, index, engine: engine || null, limit: { depth }, variant: variant || null,
    });
  }
  kbStats(): Observable<any> {
    return this.http.get(`${this.base}/kb/stats`);
  }
}
