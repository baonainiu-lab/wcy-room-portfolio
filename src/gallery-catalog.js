import development from './content/gallery-exhibits-23.json' with { type: 'json' };
import practice from './content/gallery-exhibits-45.json' with { type: 'json' };

export const galleryExhibits = [
  { index: 1, slug: 'sugar-shell-glutton', title: '糖壳暴食兽', subtitle: '3D 玩法原型',
    eyebrow: '01 / GAME PROTOTYPE', cover: '/media/works/sugar-shell-glutton/poster.webp', items: [] },
  ...development, ...practice,
];
export const getGalleryExhibit = index => galleryExhibits.find(exhibit => exhibit.index === Number(index));
export const galleryFocusId = index => `gallery.work.${String(index).padStart(2, '0')}${[1, 3].includes(index) ? '.art' : ''}`;
