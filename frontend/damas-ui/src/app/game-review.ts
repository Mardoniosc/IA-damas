import { Component, computed, HostListener, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { BOARD_SIZE, moveSquares } from './board';
import { BoardView } from './board-view';

/** Upload a PDN file (e.g. a PlayOK export), pick a game, analyse it, step through the moves. */
@Component({
  selector: 'app-game-review',
  imports: [FormsModule, BoardView],
  templateUrl: './game-review.html',
  styleUrl: './game-review.css',
})
export class GameReview {
  private readonly api = inject(ApiService);
  readonly engines = input<any[]>([]);

  readonly pdn = signal('');
  readonly fileName = signal<string | null>(null);
  readonly games = signal<any[]>([]);
  readonly selected = signal<number | null>(null);
  readonly engine = signal<string>('');
  readonly depth = signal(5);
  readonly review = signal<any | null>(null);
  readonly ply = signal(0); // index into plies; plies.length = final position
  readonly busy = signal<string | null>(null);
  readonly error = signal<string | null>(null);

  readonly selectedGame = computed(() => this.games().find((g) => g.index === this.selected()) ?? null);
  readonly variantEngines = computed(() => {
    const v = this.selectedGame()?.variant;
    return this.engines().filter((e) => e.native_variant === v);
  });
  readonly size = computed(() => BOARD_SIZE[this.review()?.game?.variant ?? 'brazilian-8x8'] ?? 8);
  readonly plies = computed<any[]>(() => this.review()?.plies ?? []);
  readonly current = computed(() => {
    const i = this.ply();
    return i < this.plies().length ? this.plies()[i] : null;
  });
  readonly fen = computed(() => this.current()?.fen_before ?? this.review()?.final_fen ?? '');
  readonly playedSquares = computed(() => moveSquares(this.current()?.played?.numeric));
  readonly bestSquares = computed(() => {
    const c = this.current();
    return c && c.best && c.best.numeric !== c.played.numeric ? moveSquares(c.best.numeric) : [];
  });
  readonly rows = computed(() => {
    const out: { n: number; w: any; wi: number; b: any; bi: number }[] = [];
    this.plies().forEach((p, i) => {
      if (p.side === 'W' || !out.length || out[out.length - 1].b) {
        out.push({ n: p.move_number, w: p.side === 'W' ? p : null, wi: p.side === 'W' ? i : -1, b: null, bi: -1 });
      }
      if (p.side === 'B') {
        const row = out[out.length - 1];
        row.b = p;
        row.bi = i;
      }
    });
    return out;
  });
  readonly players = computed(() => Object.entries(this.review()?.summary ?? {}).map(([name, s]) => ({ name, s: s as any })));

  async onFile(event: Event): Promise<void> {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.fileName.set(file.name);
    this.pdn.set(await file.text());
    await this.load();
  }

  async load(): Promise<void> {
    this.error.set(null);
    this.review.set(null);
    this.selected.set(null);
    await this.run('loading games', async () => {
      const r = await firstValueFrom(this.api.parseGames(this.pdn()));
      this.games.set(r.games);
      if (!r.games.length) this.error.set('No games found in this text.');
    });
  }

  choose(index: number): void {
    this.selected.set(index);
    this.review.set(null);
    const ids = this.variantEngines().map((e) => e.engine_id);
    if (!ids.includes(this.engine())) this.engine.set(ids[0] ?? '');
  }

  async analyse(): Promise<void> {
    const g = this.selectedGame();
    if (!g) return;
    this.review.set(null);
    await this.run('analysing (this can take a few seconds)', async () => {
      this.review.set(await firstValueFrom(this.api.analyzeGame(this.pdn(), g.index, this.engine() || null, this.depth())));
      this.ply.set(0);
    });
  }

  go(i: number): void {
    this.ply.set(Math.max(0, Math.min(i, this.plies().length)));
  }

  @HostListener('window:keydown', ['$event'])
  onKey(e: KeyboardEvent): void {
    if (!this.review() || (e.target as HTMLElement)?.tagName === 'TEXTAREA' || (e.target as HTMLElement)?.tagName === 'INPUT') return;
    if (e.key === 'ArrowRight') this.go(this.ply() + 1);
    else if (e.key === 'ArrowLeft') this.go(this.ply() - 1);
    else if (e.key === 'Home') this.go(0);
    else if (e.key === 'End') this.go(this.plies().length);
    else return;
    e.preventDefault();
  }

  private async run(label: string, fn: () => Promise<void>): Promise<void> {
    this.busy.set(label);
    try {
      await fn();
    } catch (e) {
      const err = e as { error?: { detail?: unknown }; message?: string };
      const d = err?.error?.detail;
      this.error.set(typeof d === 'string' ? d : JSON.stringify(d ?? err?.message ?? e));
    } finally {
      this.busy.set(null);
    }
  }
}
