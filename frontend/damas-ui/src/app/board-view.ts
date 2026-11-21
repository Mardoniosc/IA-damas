import { Component, computed, input } from '@angular/core';

import { parseFen } from './board';

/** Read-only SVG board. ``played`` squares get a blue frame, ``best`` squares a green one. */
@Component({
  selector: 'app-board-view',
  template: `
    @if (board(); as b) {
      <svg [attr.viewBox]="'0 0 ' + size() * 50 + ' ' + size() * 50" class="board" role="img"
           [attr.aria-label]="'board, ' + (b.sideToMove === 'W' ? 'White' : 'Black') + ' to move'">
        @for (rank of cells(); track rank) {
          @for (file of cells(); track file) {
            <rect [attr.x]="file * 50" [attr.y]="y(rank)" width="50" height="50"
                  [class.dark]="(file + rank) % 2 === 0" [class.light]="(file + rank) % 2 === 1" />
          }
        }
        @for (s of b.squares; track s.number) {
          @if (bestSet().has(s.number)) {
            <rect class="best" [attr.x]="s.file * 50 + 2" [attr.y]="y(s.rank) + 2" width="46" height="46" />
          }
          @if (playedSet().has(s.number)) {
            <rect class="played" [attr.x]="s.file * 50 + 5" [attr.y]="y(s.rank) + 5" width="40" height="40" />
          }
          <text class="num" [attr.x]="s.file * 50 + 3" [attr.y]="y(s.rank) + 11">{{ s.number }}</text>
          @if (s.piece) {
            <circle [attr.cx]="s.file * 50 + 25" [attr.cy]="y(s.rank) + 25" r="18"
                    [class.white]="s.piece === 'w' || s.piece === 'W'" [class.black]="s.piece === 'b' || s.piece === 'B'" />
            @if (s.piece === 'W' || s.piece === 'B') {
              <text class="king" [attr.x]="s.file * 50 + 25" [attr.y]="y(s.rank) + 31">K</text>
            }
          }
        }
      </svg>
      <p class="caption">{{ b.sideToMove === 'W' ? 'White' : 'Black' }} to move</p>
    } @else {
      <p class="error">Invalid position.</p>
    }
  `,
  styles: `
    .board { width: 100%; height: auto; border: 1px solid var(--line); display: block; }
    rect.dark { fill: var(--dark-sq); } rect.light { fill: var(--light-sq); }
    rect.played { fill: none; stroke: var(--accent); stroke-width: 4; }
    rect.best { fill: none; stroke: #2e9e4f; stroke-width: 4; stroke-dasharray: 6 3; }
    circle.white { fill: #f6f1e7; stroke: #555; stroke-width: 2; }
    circle.black { fill: #2b2b2b; stroke: #000; stroke-width: 2; }
    text.num { font-size: 9px; fill: var(--num); }
    text.king { font-size: 16px; font-weight: 700; text-anchor: middle; fill: #c9302c; }
    .caption { font-size: 13px; color: var(--muted); } .error { color: #b3261e; }
  `,
})
export class BoardView {
  readonly fen = input.required<string>();
  readonly size = input(8);
  readonly played = input<number[]>([]);
  readonly best = input<number[]>([]);

  readonly cells = computed(() => Array.from({ length: this.size() }, (_, i) => i));
  readonly board = computed(() => {
    try {
      return parseFen(this.fen(), this.size());
    } catch {
      return null;
    }
  });
  readonly playedSet = computed(() => new Set(this.played()));
  readonly bestSet = computed(() => new Set(this.best()));

  y(rank: number): number {
    return (this.size() - 1 - rank) * 50;
  }
}
