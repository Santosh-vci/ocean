import { Presentation, layers, text, shape } from 'file:///C:/Users/santosh%20(07564B3B)/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const pres = Presentation.create();
const slide = pres.slides.add({ width: 1600, height: 900 });
slide.compose(layers({ width: 1600, height: 900 }, [
  shape({ position: { x: 0, y: 0 }, width: 1600, height: 900, fill: '#FFFFFF' }),
  shape({ position: { x: 0, y: 0 }, width: 1600, height: 90, fill: '#0B2948' }),
  text('Probe Slide', { position: { x: 72, y: 32 }, width: 700, height: 60, style: { fontSize: 34, fontFace: 'Segoe UI', color: '#FFFFFF', bold: true } })
]));
const png = await slide.export({ format: 'png' });
await png.save('F:/ocean/outputs/manual-abl-presentation/presentations/abl-client-deck/probe.png');
console.log('saved png');
