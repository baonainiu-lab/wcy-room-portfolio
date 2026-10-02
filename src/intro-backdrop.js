import * as THREE from 'three';

// Abstract light in the existing sky/ground pass: no background picture,
// scene props, second canvas, postprocessing pass or independent RAF loop.
export function createIntroBackdrop({ texture, renderer, view, paper }) {
  const resolution = new THREE.Vector2(1, 1);
  const reveal = { value: 1 }, clock = { value: 0 };
  const uniforms = {
    uIntroResolution: { value: resolution },
    uIntroPaper: { value: paper },
    uIntroBackdropReveal: reveal,
    uIntroLightTime: clock,
    uIntroPearl: { value: new THREE.Color('#e4eaf0') },
    uIntroSlate: { value: new THREE.Color('#8ea9c7') },
    uIntroInk: { value: new THREE.Color('#1a3152') },
    uIntroSilver: { value: new THREE.Color('#eff8ff') },
    uIntroChampagne: { value: new THREE.Color('#d8b38b') },
  };
  const declarations = `
uniform vec2 uIntroResolution;
uniform vec3 uIntroPaper;
uniform float uIntroBackdropReveal;
uniform float uIntroLightTime;
uniform vec3 uIntroPearl;
uniform vec3 uIntroSlate;
uniform vec3 uIntroInk;
uniform vec3 uIntroSilver;
uniform vec3 uIntroChampagne;
float introLightBand(float distanceToLine, float width) {
  float d = distanceToLine / max(width, 0.0001);
  return exp(-d * d);
}
vec3 introBackdropColor() {
  vec2 uv = gl_FragCoord.xy / uIntroResolution;
  float t = uIntroLightTime;
  float px = 1.0 / uIntroResolution.y;
  float diagonal = clamp(uv.x * .52 + uv.y * .62, 0.0, 1.0);
  vec3 color = mix(uIntroSlate, uIntroPearl, smoothstep(.15, .85, diagonal));
  float ink = (1.0 - smoothstep(-.08, .57, uv.x)) * (1.0 - smoothstep(.05, .87, uv.y));
  color = mix(color, uIntroInk, ink * .89);
  float broad = introLightBand(uv.y - .68 + .16 * sin(uv.x * 3.1 + t * .13), .28);
  color = mix(color, uIntroSilver, broad * .14);

  // A colour body, a soft rim and a clear highlight form each light ribbon.
  float routeA = .06 + .32 * pow(uv.x, 1.5) + .038 * sin(uv.x * 4.3 - t * .18);
  float dA = uv.y - routeA;
  color = mix(color, uIntroInk, introLightBand(dA + .068, .055) * .24);
  color = mix(color, uIntroSlate, introLightBand(dA, .10) * .36);
  float travelA = .53 + .47 * sin(uv.x * 5.2 - t * .44);
  color = mix(color, uIntroSilver, introLightBand(dA, max(px * 4.5, .0055)) * (.47 + .42 * travelA));
  color = mix(color, uIntroSilver, introLightBand(dA, .024) * .22);

  float routeB = .96 - .54 * pow(1.0 - uv.x, 2.0) + .036 * sin(uv.x * 3.2 + t * .15 + 1.4);
  float dB = uv.y - routeB;
  float fadeB = 1.0 - smoothstep(.57, .95, uv.x);
  color = mix(color, uIntroSlate, introLightBand(dB - .042, .047) * .26 * fadeB);
  color = mix(color, uIntroSilver, introLightBand(dB, max(px * 3.6, .0045)) * .78 * fadeB);
  color = mix(color, uIntroSilver, introLightBand(dB, .038) * .25 * fadeB);

  float routeC = routeA - .043 - .015 * sin(uv.x * 5.0 + t * .12);
  float accent = introLightBand(uv.y - routeC, max(px * 2.6, .0035));
  float sweep = pow(.5 + .5 * sin(uv.x * 5.6 - t * .37 - 1.2), 2.0);
  color = mix(color, uIntroChampagne, accent * (.3 + .38 * sweep));
  color = mix(color, uIntroChampagne, introLightBand(uv.y - routeC, .04) * .07 * sweep);
  // A stable title field prevents moving light from reducing text contrast.
  float copyQuiet = smoothstep(.65, .94, uv.x) * introLightBand(uv.y - .52, .31);
  color = mix(color, uIntroPearl, copyQuiet * .5);
  return mix(uIntroPaper, color, uIntroBackdropReveal);
}
`;
  return {
    declarations,
    reveal,
    bind(shader) { Object.assign(shader.uniforms, uniforms); },
    unbind(shader) { for (const name of Object.keys(uniforms)) delete shader.uniforms[name]; },
    update(seconds, reducedMotion = false) { clock.value = reducedMotion ? 0 : seconds; },
    resize() {
      if (renderer.getDrawingBufferSize) renderer.getDrawingBufferSize(resolution);
      else resolution.set(view.innerWidth, view.innerHeight);
    },
    dispose() { texture?.dispose(); },
  };
}
