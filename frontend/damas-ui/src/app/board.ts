/**
 * Board model for the UI. Pure functions, no Angular dependency, so they are easy to test.
 *
 * Numeric (PDN) squares follow the backend convention (docs/architecture/position-representation.md):
 * square 1 is the leftmost playable square of the top row as seen by White; numbering runs left to
 * right, top to bottom; a1 is dark (8x8: a1 = 29, 10x10: a1 = 46).
 */

export type Piece = 'w' | 'W' | 'b' | 'B';

export interface BoardSquare {
  number: number; // PDN numeric square
  file: number; // 0-based from the left (White's view)
  rank: number; // 0-based from White's side
  piece: Piece | null;
}

export interface ParsedFen {
  size: number;
  sideToMove: 'W' | 'B';
  squares: BoardSquare[];
}

export function squareCoords(size: number, n: number): { file: number; rank: number } {
  const half = size / 2;
  const rowFromTop = Math.floor((n - 1) / half);
  const col = (n - 1) % half;
  const rank = size - 1 - rowFromTop;
  const file = 2 * col + (rank % 2);
  return { file, rank };
}

/** Parse a PDN FEN such as "W:W21-32:B1-12" or "B:WK29,22:BK1,10". */
export function parseFen(fen: string, size: number): ParsedFen {
  const text = fen.replace(/^\[FEN\s+"/, '').replace(/"\]$/, '').trim();
  const fields = text.split(':');
  if (fields.length !== 3 || !/^[WB]$/i.test(fields[0])) {
    throw new Error(`bad FEN: ${fen}`);
  }
  const total = (size * size) / 2;
  const pieces = new Map<number, Piece>();
  for (const field of fields.slice(1)) {
    const f = field.trim();
    if (!f) continue;
    const color = f[0].toUpperCase();
    for (const raw of f.slice(1).split(',').map((s) => s.trim()).filter(Boolean)) {
      const king = raw.toUpperCase().startsWith('K');
      const item = raw.replace(/^[Kk]/, '');
      const [lo, hi] = item.split('-').map((x) => parseInt(x, 10));
      for (let n = lo; n <= (hi || lo); n++) {
        if (n < 1 || n > total) throw new Error(`square ${n} out of range`);
        pieces.set(n, (color === 'W' ? (king ? 'W' : 'w') : king ? 'B' : 'b') as Piece);
      }
    }
  }
  const squares: BoardSquare[] = [];
  for (let n = 1; n <= total; n++) {
    squares.push({ number: n, ...squareCoords(size, n), piece: pieces.get(n) ?? null });
  }
  return { size, sideToMove: fields[0].toUpperCase() as 'W' | 'B', squares };
}

/** Squares mentioned in a numeric move ("32-28", "28x19x10"). */
export function moveSquares(move: string | null | undefined): number[] {
  if (!move) return [];
  return move.split(/[-x]/).map((s) => parseInt(s, 10)).filter((n) => !Number.isNaN(n));
}

export const START_FEN: Record<string, string> = {
  'brazilian-8x8': 'W:W21-32:B1-12',
  'international-10x10': 'W:W31-50:B1-20',
};

export const BOARD_SIZE: Record<string, number> = { 'brazilian-8x8': 8, 'international-10x10': 10 };
