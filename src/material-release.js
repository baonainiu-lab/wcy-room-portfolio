// Select the configured local release as a whole. Individual scenes retain
// their approved shading path; the restored V5 gallery is intentionally sRGB.
// ?physicalPreview=0 remains an explicit route to the previous complete release.
export const PHYSICAL_MATERIALS_DEFAULT = true;

const RELEASES = Object.freeze({
  legacy: Object.freeze({
    physical: false, galleryPhysical: false, name: 'room16-gallery5-terminal2', aboutApprovedUnchanged: true,
    roomModel: '/models/orbital-atelier-v16-compressed.glb', roomRevision: 16,
    roomDirectory: '/textures/lighting-v16', introDirectory: '/textures/intro-clean-v16',
    galleryModel: '/models/works-gallery-v5-compressed.glb', galleryRevision: 'gallery-5',
    galleryDirectory: '/textures/works-gallery-v5', terminalModel: '/models/welcome-terminal-v2.glb', terminalRevision: 2,
  }),
  physical: Object.freeze({
    physical: true, galleryPhysical: false, name: 'room20-gallery5-terminal3', aboutApprovedUnchanged: true,
    radiance: Object.freeze({ encoding: 'logrgb', radianceRange: 32, logGain: 256 }),
    roomNightRadianceScale: Object.freeze({ 0: 2, 1: 2, 2: 2, 4: 8, 12: 128 }),
    roomModel: '/models/orbital-atelier-v20-compressed.glb', roomRevision: 20, roomAtlasCount: 13,
    roomDirectory: '/textures/lighting-v20', introDirectory: '/textures/intro-clean-v20',
    galleryModel: '/models/works-gallery-v5-compressed.glb', galleryRevision: 'gallery-5',
    galleryDirectory: '/textures/works-gallery-v5', terminalModel: '/models/welcome-terminal-v3-compressed.glb', terminalRevision: 3,
  }),
});

export function resolveMaterialRelease(search = '', enabledByDefault = PHYSICAL_MATERIALS_DEFAULT) {
  const params = new URLSearchParams(search);
  const enabled = params.has('physicalPreview')
    ? !['0', 'false', 'off'].includes(params.get('physicalPreview').toLowerCase()) : enabledByDefault;
  return RELEASES[enabled ? 'physical' : 'legacy'];
}
