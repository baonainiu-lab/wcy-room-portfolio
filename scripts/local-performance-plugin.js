// Development-only diagnostics for verifying the requested 120 FPS budget.
// Data stays in this localhost Vite process; nothing is sent to an external service.
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

export function localPerformancePlugin() {
  const sessions = new Map();
  let pendingCapture = null;
  let outputDirectory;
  const client = `
const session=crypto.randomUUID();
let renderer,original,pending=[],extension,gl,sampling,lastPost=0,cpu=[],gpu=[],frames=0,captureName=null,ready=false,frameQuery=null,frameCpu=0,frameOpen=false;
function quantiles(a){if(!a.length)return null;const s=[...a].sort((a,b)=>a-b);return {p50:s[Math.floor(s.length*.5)],p95:s[Math.min(s.length-1,Math.floor(s.length*.95))],max:s.at(-1),samples:s.length};}
function install(){
 const d=window.__roomPreview;if(!d?.renderer){setTimeout(install,250);return;}
 renderer=d.renderer;gl=renderer.getContext();extension=gl.getExtension('EXT_disjoint_timer_query_webgl2');original=renderer.render;
 renderer.render=function(...args){
  const offscreen=renderer.getRenderTarget()!==null;
  const active=ready&&!document.hidden&&(!offscreen||d.transitionActive);
  if(active&&!frameOpen){frameOpen=true;frameCpu=0;if(extension&&++frames%4===0&&pending.length<10){frameQuery=gl.createQuery();gl.beginQuery(extension.TIME_ELAPSED_EXT,frameQuery);}}
  const start=performance.now();const result=original.apply(this,args);const ms=performance.now()-start;
  if(active)frameCpu+=ms;
  if(!offscreen&&frameOpen){cpu.push(frameCpu);if(cpu.length>240)cpu.shift();if(frameQuery){gl.endQuery(extension.TIME_ELAPSED_EXT);pending.push(frameQuery);frameQuery=null;}frameOpen=false;}
  if(captureName&&active&&!offscreen){const name=captureName;captureName=null;const png=renderer.domElement.toDataURL('image/png');fetch('/__preview_capture/'+name,{method:'POST',headers:{'Content-Type':'text/plain'},body:png}).catch(()=>{});}
  return result;
 };
 setInterval(()=>{
  if(extension){const disjoint=gl.getParameter(extension.GPU_DISJOINT_EXT);pending=pending.filter(q=>{if(!gl.getQueryParameter(q,gl.QUERY_RESULT_AVAILABLE))return true;if(!disjoint){gpu.push(gl.getQueryParameter(q,gl.QUERY_RESULT)/1e6);if(gpu.length>120)gpu.shift();}gl.deleteQuery(q);return false;});}
  const state=d.getState();ready=(state.homepage?.active)||(state.entered&&state.introComplete);if(!ready||document.hidden)return;
  sampling ||= {antialias:gl.getContextAttributes().antialias,samples:gl.getParameter(gl.SAMPLES),maxAnisotropy:renderer.capabilities.getMaxAnisotropy()};
  const info={session,time:Date.now(),userAgent:navigator.userAgent,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,renderDpr:renderer.getPixelRatio(),drawingBuffer:[renderer.domElement.width,renderer.domElement.height],sampling,baked:state.baked,day:state.day,uiRevision:state.uiRevision,phase:state.homepage?.active?'homepage':state.currentScene??'room',gallery:state.gallery,transitioning:state.transitioning,transition:state.transition,homepage:state.homepage,motion:state.motion,liveSurfaces:state.liveSurfaces,cameraGuard:state.cameraGuard,activeSection:state.activeSection,callout:state.callout,roomTextures:state.roomTextures,lightingRevision:state.lightingRevision,lighting:state.lighting,triangles:state.triangles,drawCalls:state.drawCalls,assetCount:state.assetCount,componentCount:state.componentCount,errors:state.errors,hovered:state.hovered,camera:state.camera,target:state.target,modal:state.modal,lastInteraction:state.lastInteraction,raf:state.performance,cpuMs:quantiles(cpu),gpuMs:quantiles(gpu)};
  window.__localPerformance=info;
  if(performance.now()-lastPost>(state.transitioning?250:5000)){lastPost=performance.now();fetch('/__preview_metrics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(info)}).then(r=>r.json()).then(data=>{if(data.capture)captureName=data.capture;}).catch(()=>{});}
 },250);
}
install();
`;
  return {
    name: 'local-performance-measurement',
    apply: 'serve',
    transformIndexHtml() { return [{tag:'script',attrs:{type:'module',src:'/@local-preview-performance.js'},injectTo:'body'}]; },
    configureServer(server) {
      outputDirectory = resolve(server.config.root, 'renders');
      server.middlewares.use((req,res,next)=>{
        if(req.url==='/@local-preview-performance.js'){res.setHeader('Content-Type','text/javascript');res.end(client);return;}
        if(req.url?.startsWith('/__preview_capture/')){
          const name=req.url.slice('/__preview_capture/'.length);
          if(!/^[a-z0-9-]{1,80}$/.test(name)){res.statusCode=400;res.end('{}');return;}
          if(req.method==='GET'){pendingCapture=name;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({queued:name}));return;}
          if(req.method!=='POST'){res.statusCode=405;res.end('{}');return;}
          let body='';req.on('data',chunk=>{body+=chunk;if(body.length>16000000)req.destroy();});
          req.on('end',async()=>{try{if(!body.startsWith('data:image/png;base64,'))throw Error();await mkdir(outputDirectory,{recursive:true});await writeFile(resolve(outputDirectory,name+'.png'),Buffer.from(body.slice(22),'base64'));res.end('{}');}catch{res.statusCode=400;res.end('{}');}});return;
        }
        if(req.url!=='/__preview_metrics')return next();
        res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
        if(req.method==='GET'){res.end(JSON.stringify([...sessions.values()]));return;}
        if(req.method!=='POST'){res.statusCode=405;res.end('{}');return;}
        let body='';req.on('data',chunk=>{body+=chunk;if(body.length>16384)req.destroy();});req.on('end',()=>{try{const data=JSON.parse(body);if(typeof data.session!=='string')throw Error();sessions.set(data.session,data);while(sessions.size>12)sessions.delete(sessions.keys().next().value);const capture=pendingCapture;pendingCapture=null;res.end(JSON.stringify({capture}));}catch{res.statusCode=400;res.end('{}');}});
      });
    },
  };
}
