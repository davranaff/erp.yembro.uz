/**
 * Code128-B SVG encoder — no external dependencies.
 *
 * Encodes ASCII 32–126 using Code128-B encoding.
 * Returns a self-contained SVG string ready for dangerouslySetInnerHTML or img src.
 */

// Code128 bar/space pattern table.
// Each entry is 6 digits (bar, space, bar, space, bar, space widths 1-4).
// Indices 0-102 = symbols, 103 = START B (index 104), 106 = STOP.
const PATTERNS: readonly string[] = [
  '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312',
  '132212', '221213', '221312', '231212', '112232', '122132', '122231', '113222',
  '123122', '123221', '223211', '221132', '221231', '213212', '223112', '312131',
  '311222', '321122', '321221', '312212', '322112', '322211', '212123', '212321',
  '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
  '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121',
  '313121', '211331', '231131', '213113', '213311', '213131', '311123', '311321',
  '331121', '312113', '312311', '332111', '314111', '221411', '431111', '111224',
  '111422', '121124', '121421', '141122', '141221', '112214', '112412', '122114',
  '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
  '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112',
  '421211', '212141', '214121', '412121', '111143', '111341', '131141', '114113',
  '114311', '411113', '411311', '113141', '114131', '311141', '411131', '211412',
  '211214', '211232', '2331112',
];

const START_B = 104;
const STOP    = 106;

function widths(symbol: number): number[] {
  return PATTERNS[symbol].split('').map(Number);
}

export function encode128svg(
  text: string,
  opts?: { height?: number; moduleWidth?: number; quiet?: number },
): string {
  const h   = opts?.height      ?? 64;
  const mw  = opts?.moduleWidth ?? 2;
  const q   = opts?.quiet       ?? 10;

  // Build symbol list: START_B, data, checksum, STOP
  const values: number[] = [START_B];
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code < 32 || code > 126) continue; // skip non-Code128B chars
    values.push(code - 32);
  }

  // Check digit
  let checksum = START_B;
  for (let i = 1; i < values.length; i++) {
    checksum += values[i] * i;
  }
  values.push(checksum % 103);
  values.push(STOP);

  // Flatten all widths into a bar/space sequence
  const bars: number[] = [];
  for (const v of values) {
    bars.push(...widths(v));
  }
  // STOP has an extra 2-module terminator bar at the end (already in pattern '2331112')

  // Calculate total pixel width
  const totalModules = bars.reduce((a, b) => a + b, 0);
  const svgW = q * 2 + totalModules * mw;
  const textY = h + 14;
  const svgH = textY + 4;

  // Build SVG rects
  let rects = '';
  let x = q;
  for (let i = 0; i < bars.length; i++) {
    const w = bars[i] * mw;
    if (i % 2 === 0) {
      // odd-indexed steps are bars (black)
      rects += `<rect x="${x}" y="0" width="${w}" height="${h}" fill="#000"/>`;
    }
    x += w;
  }

  // Human-readable text below
  const label = `<text x="${svgW / 2}" y="${textY}" text-anchor="middle" `
    + `font-family="monospace" font-size="11" fill="#111">${escXml(text)}</text>`;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${svgW}" height="${svgH}" `
    + `viewBox="0 0 ${svgW} ${svgH}">`
    + `<rect width="${svgW}" height="${svgH}" fill="#fff"/>`
    + rects
    + label
    + `</svg>`;
}

function escXml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
