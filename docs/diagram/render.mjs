// Render one SVG to PNG with resvg: node render.mjs <in.svg> <out.png> <zoom> <background>
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';

const { Resvg } = createRequire(import.meta.url)('@resvg/resvg-js');
const [src, dst, zoom, background] = process.argv.slice(2);
const png = new Resvg(readFileSync(src, 'utf8'), {
  fitTo: { mode: 'zoom', value: Number(zoom) },
  font: { loadSystemFonts: true, defaultFontFamily: 'Helvetica Neue' },
  background,
}).render();
writeFileSync(dst, png.asPng());
console.log(`${dst}: ${png.width}x${png.height}`);
