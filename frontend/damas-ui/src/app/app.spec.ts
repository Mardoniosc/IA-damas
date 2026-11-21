import { describe, expect, it } from 'vitest';

import { moveSquares, parseFen, squareCoords } from './board';

describe('board model (mirrors backend numbering)', () => {
  it('maps numeric squares like the backend: a1 = 29 (8x8), a1 = 46 (10x10)', () => {
    expect(squareCoords(8, 29)).toEqual({ file: 0, rank: 0 });
    expect(squareCoords(8, 4)).toEqual({ file: 7, rank: 7 });
    expect(squareCoords(10, 46)).toEqual({ file: 0, rank: 0 });
  });

  it('parses start positions with ranges and kings', () => {
    const br = parseFen('W:W21-32:B1-12', 8);
    expect(br.squares.filter((s) => s.piece === 'w').length).toBe(12);
    expect(br.squares.filter((s) => s.piece === 'b').length).toBe(12);
    const k = parseFen('B:WK29:BK4,10', 8);
    expect(k.sideToMove).toBe('B');
    expect(k.squares[28].piece).toBe('W');
    expect(() => parseFen('nonsense', 8)).toThrow();
  });

  it('extracts squares from numeric moves', () => {
    expect(moveSquares('28x19x10')).toEqual([28, 19, 10]);
    expect(moveSquares(null)).toEqual([]);
  });
});
