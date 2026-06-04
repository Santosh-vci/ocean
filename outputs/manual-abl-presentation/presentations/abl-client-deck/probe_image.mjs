import fs from 'node:fs/promises';
import { Presentation, PresentationFile, layers, image, shape } from 'file:///C:/Users/santosh%20(07564B3B)/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const data = await fs.readFile('F:/ocean/docs/proposal/final_version/ABL_Program_Delivery_Timeline_Gantt_v2.png');
const pres = Presentation.create();
const slide = pres.slides.add({ width: 1600, height: 900 });
slide.compose(layers({ width: 1600, height: 900 }, [
  shape({ position: {x:0,y:0}, width:1600, height:900, fill:'#FFFFFF' }),
  image({ data, contentType: 'image/png', position: { x: 80, y: 120 }, width: 1440, height: 620, fit: 'contain' })
]));
const blob = await PresentationFile.exportPptx(pres);
await blob.save('F:/ocean/outputs/manual-abl-presentation/presentations/abl-client-deck/probe_image.pptx');
console.log('image saved');
