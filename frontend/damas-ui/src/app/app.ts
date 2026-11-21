import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { BOARD_SIZE, START_FEN, moveSquares, parseFen } from './board';
import { BoardView } from './board-view';
import { GameReview } from './game-review';

@Component({
  selector: 'app-root',
  imports: [FormsModule, BoardView, GameReview],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  private readonly api = inject(ApiService);

  readonly tab = signal<'position' | 'review'>('position');
  readonly variant = signal('brazilian-8x8');
  readonly fen = signal(START_FEN['brazilian-8x8']);
  readonly moveTime = signal(0.2);
  readonly depth = signal(5);

  readonly variants = signal<any[]>([]);
  readonly engines = signal<any[]>([]);
  readonly kb = signal<any | null>(null);
  readonly decision = signal<any | null>(null);
  readonly tactics = signal<any | null>(null);
  readonly strategy = signal<any | null>(null);
  readonly busy = signal<string | null>(null);
  readonly error = signal<string | null>(null);

  readonly size = computed(() => BOARD_SIZE[this.variant()] ?? 8);
  readonly board = computed(() => {
    try {
      return parseFen(this.fen(), this.size());
    } catch {
      return null;
    }
  });
  readonly highlighted = computed(() => moveSquares(this.decision()?.move?.numeric));
  readonly variantInfo = computed(() => this.variants().find((v) => v.variant === this.variant()));

  constructor() {
    void this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      this.variants.set(await firstValueFrom(this.api.variants()));
      this.engines.set(await firstValueFrom(this.api.engines()));
    } catch (e) {
      this.error.set(`backend unreachable: ${this.message(e)}`);
    }
    try {
      this.kb.set(await firstValueFrom(this.api.kbStats()));
    } catch {
      this.kb.set(null); // knowledge base not configured: optional
    }
  }

  setVariant(v: string): void {
    this.variant.set(v);
    this.fen.set(START_FEN[v]);
    this.clear();
  }

  clear(): void {
    this.decision.set(null);
    this.tactics.set(null);
    this.strategy.set(null);
    this.error.set(null);
  }

  async analyse(): Promise<void> {
    this.clear();
    await this.run('decision', async () => {
      this.decision.set(await firstValueFrom(this.api.decision(this.variant(), this.fen(), this.moveTime())));
    });
    await this.run('tactics', async () => {
      this.tactics.set(await firstValueFrom(this.api.tactics(this.variant(), this.fen(), this.depth())));
      this.strategy.set(await firstValueFrom(this.api.strategy(this.variant(), this.fen())));
    });
    await this.refresh();
  }

  regretList(c: any): { engine: string; value: string }[] {
    return Object.entries(c.normalized_regret ?? {}).map(([engine, v]) => ({
      engine,
      value: v === null || v === undefined ? 'n/a' : Number(v).toFixed(2),
    }));
  }

  private async run(label: string, fn: () => Promise<void>): Promise<void> {
    this.busy.set(label);
    try {
      await fn();
    } catch (e) {
      this.error.set(`${label}: ${this.message(e)}`);
    } finally {
      this.busy.set(null);
    }
  }

  private message(e: unknown): string {
    const err = e as { error?: { detail?: unknown }; message?: string };
    const detail = err?.error?.detail;
    return typeof detail === 'string' ? detail : JSON.stringify(detail ?? err?.message ?? e);
  }
}
