// Trusted renderer: inputs are generated, validated local composition files.
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {selectComposition, renderMedia} from '@remotion/renderer';
const [workspace,output]=process.argv.slice(2);
if(!workspace||!output)throw new Error('Usage: render.mjs workspace output.mp4');
const serveUrl=await bundle({entryPoint:path.join(workspace,'index.tsx'),publicDir:path.join(workspace,'public'),
  webpackOverride:config=>config});
const composition=await selectComposition({serveUrl,id:'Cutroom',logLevel:'error'});
let last=-1;
await renderMedia({serveUrl,composition,outputLocation:output,codec:'h264',pixelFormat:'yuv420p',
  hardwareAcceleration:'if-possible',concurrency:2,logLevel:'error',overwrite:true,
  onProgress:({progress})=>{const p=Math.floor(progress*10)*10;if(p!==last){last=p;console.log(`Remotion ${p}%`);}}});
console.log(JSON.stringify({output,duration:composition.durationInFrames/composition.fps}));
