import fs from 'node:fs/promises';
import { chromium } from '/Users/a90/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-webgl','--ignore-gpu-blocklist']});
const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1});
const errors=[];const failed=[];page.on('pageerror',e=>errors.push(String(e)));page.on('response',r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()})});
await page.goto('http://127.0.0.1:5173/',{waitUntil:'networkidle'});
await page.waitForFunction(()=>window.__roomPreview?.getState().loaded,null,{timeout:60000});
await page.locator('.loading-screen-button').click();await page.waitForFunction(()=>window.__roomPreview.getState().controlsEnabled);
const checks=[];
for(const kind of ['work','about','contact']){
 await page.locator(`.main-nav [data-modal="${kind}"]`).click();await page.waitForTimeout(550);
 const v=await page.evaluate(()=>({state:window.__roomPreview.getState(),text:document.querySelector('#modal-content').textContent}));
 if(v.state.modal!==kind||!v.text.includes('待补充')||v.state.controlsEnabled)throw Error('Modal failed: '+kind);
 checks.push({test:'nav '+kind,passed:true});await page.keyboard.press('Escape');await page.waitForTimeout(350);
}
// Find real visible pixels for each logical object using its model geometry and camera.
const pixels=await page.evaluate(async()=>{
 const T=await import('/node_modules/three/build/three.module.js');const d=window.__roomPreview;const found={};const ray=new T.Raycaster();const v=new T.Vector2();
 d.scene.updateMatrixWorld(true);d.camera.updateMatrixWorld(true);
 const meshes=[];d.room.traverse(n=>{if(n.isMesh)meshes.push(n)});
 for(let y=200;y<870;y+=8)for(let x=200;x<1240;x+=8){v.set(x/innerWidth*2-1,1-y/innerHeight*2);ray.setFromCamera(v,d.camera);const hit=ray.intersectObjects(meshes,false)[0];if(!hit)continue;for(let o=hit.object;o&&o!==d.room;o=o.parent){const id=o.userData.asset_id;if(d.roots.has(id)){if(!found[id])found[id]={x,y};break}}}
 return found;
});
for(const id of ['robot_companion','main_display','compact_camera','studio_reference_books','geometric_specimen_cloche','portable_fold_communicator','ceramic_mobius_study','glass_cutting_planter']){
 const pos=pixels[id];if(!pos)throw Error('No visible geometry: '+id);await page.mouse.move(pos.x,pos.y);await page.waitForTimeout(400);await page.mouse.click(pos.x,pos.y);await page.waitForTimeout(550);
 const state=await page.evaluate(()=>window.__roomPreview.getState());if(state.modal!=='asset')throw Error('Asset click failed: '+id);
 checks.push({test:'asset '+id,passed:true,selected:state.activeAsset});await page.keyboard.press('Escape');await page.waitForTimeout(350);
}
await page.locator('.theme-toggle-button').click();await page.waitForTimeout(1250);if(!(await page.evaluate(()=>window.__roomPreview.getState().day)))throw Error('Theme failed');checks.push({test:'day theme',passed:true});await page.screenshot({path:'renders/web-day-preview.png'});
await page.locator('.mute-toggle-button').click();if(await page.evaluate(()=>window.__roomPreview.getState().muted))throw Error('Audio failed');checks.push({test:'audio toggle',passed:true});
const before=await page.evaluate(()=>window.__roomPreview.getState().camera);await page.mouse.move(900,750);await page.mouse.down();await page.mouse.move(1040,700,{steps:12});await page.mouse.up();await page.waitForTimeout(800);
const drag=await page.evaluate(()=>window.__roomPreview.getState());if(drag.modal||JSON.stringify(drag.camera)===JSON.stringify(before))throw Error('Drag failed');checks.push({test:'orbit drag without modal',passed:true});
await page.locator('.scene-controls [data-action="reset"]').click();await page.waitForTimeout(1400);const reset=await page.evaluate(()=>window.__roomPreview.getState().camera);if(Math.hypot(...reset.map((n,i)=>n-before[i]))>.01)throw Error('Reset failed');checks.push({test:'camera reset',passed:true});
await page.locator('.theme-toggle-button').click();await page.waitForTimeout(1300);
await page.setViewportSize({width:390,height:844});await page.waitForTimeout(1600);await page.screenshot({path:'renders/web-mobile-preview.png'});
const mobile=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,nav:document.querySelector('.main-nav').getBoundingClientRect().right<=innerWidth,state:window.__roomPreview.getState()}));if(mobile.overflow||!mobile.nav)throw Error('Mobile overflow');checks.push({test:'mobile framing and UI bounds',passed:true});
const report={checks,errors,failed,pixels,finalState:mobile.state};await fs.writeFile('renders/web-verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify({checks,errors,failed,mobileCamera:mobile.state.camera}));await browser.close();
