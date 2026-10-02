"""Build the approved A font for every current Chinese UI/source character.

Glyph outlines and advances are compared to the upstream file. No contour
expansion, synthetic weight, or replacement glyphs are introduced.
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset
import hashlib, json, shutil

root=Path(__file__).resolve().parents[3]
source=root/'assets/font-candidates/v4/douyin-upstream/DouyinSans/DouyinSansBold.ttf'
license_file=source.parent/'OFL.txt'
output_dir=root/'public/fonts/orbital-forge'
output_dir.mkdir(parents=True,exist_ok=True)
source_files=[root/'index.html',*sorted((root/'src').rglob('*.js')),*sorted((root/'src').rglob('*.scss')),*sorted((root/'src/content').rglob('*.json'))]
source_text=''.join(p.read_text() for p in source_files)
all_cjk={c for c in source_text if 0x3400<=ord(c)<=0x9fff}
source_punctuation={c for c in source_text if 0x2000<=ord(c)<=0x30ff or 0xff00<=ord(c)<=0xffef}
preserved=(root/'public/fonts/orbital-rounded/CHARACTERS.txt').read_text()
required=all_cjk|source_punctuation|set(preserved)|{chr(i) for i in range(32,127)}
required={c for c in required if not c.isspace() or c==' '}
font=TTFont(source);cmap=font.getBestCmap()
missing_chinese=sorted(c for c in all_cjk if ord(c) not in cmap)
assert not missing_chinese,('Missing current Chinese source characters',missing_chinese)
fallback=sorted(c for c in required if ord(c) not in cmap)
available=sorted(c for c in required if ord(c) in cmap)
before_outline={c:list(font['glyf'][cmap[ord(c)]].getCoordinates(font['glyf'])[0]) for c in available}
before_width={c:font['hmtx'][cmap[ord(c)]] for c in available}
copyrights=sorted({n.toUnicode() for n in font['name'].names if n.nameID==0})
copyright_names=[(n.nameID,n.platformID,n.platEncID,n.langID,n.toUnicode()) for n in font['name'].names if n.nameID in (0,13,14)]
original_weight=font['OS/2'].usWeightClass
removed=[]
try:font['GSUB']
except Exception:
 del font['GSUB'];removed.append('Malformed upstream GSUB: invalid lookup/subtable offset. Normal character mapping and outlines retained.')
opts=subset.Options();opts.name_IDs=['*'];opts.name_languages=['*'];opts.name_legacy=True
opts.notdef_glyph=True;opts.notdef_outline=True;opts.recommended_glyphs=True
sub=subset.Subsetter(options=opts);sub.populate(text=''.join(available));sub.subset(font)
family='Atelier Forge Display';postscript='AtelierForgeDisplay-Bold'
for record in font['name'].names:
 if record.nameID in (1,4,6,16,18,21):
  value=postscript if record.nameID==6 else family
  record.string=value.encode(record.getEncoding(),errors='replace')
 elif record.nameID==3:record.string='AtelierForgeDisplay-ProductionV1'.encode(record.getEncoding(),errors='replace')
 elif record.nameID in (2,17,22):record.string='Bold'.encode(record.getEncoding(),errors='replace')
output=output_dir/'atelier-forge-display-ui.woff2';font.flavor='woff2';font.save(output)
verified=TTFont(output);out_cmap=verified.getBestCmap()
outline_mismatch=[c for c in available if before_outline[c]!=list(verified['glyf'][out_cmap[ord(c)]].getCoordinates(verified['glyf'])[0])]
width_mismatch=[c for c in available if before_width[c]!=verified['hmtx'][out_cmap[ord(c)]]]
assert not outline_mismatch and not width_mismatch
assert original_weight==verified['OS/2'].usWeightClass
after_names=[(n.nameID,n.platformID,n.platEncID,n.langID,n.toUnicode()) for n in verified['name'].names if n.nameID in (0,13,14)]
assert copyright_names==after_names
for n in verified['name'].names:
 if n.nameID in (1,3,4,6,16,18,21):assert not any(rfn in n.toUnicode() for rfn in ['Douyin','抖音','抖音美好'])
shutil.copyfile(license_file,output_dir/'OFL.txt')
(output_dir/'CHARACTERS.txt').write_text(''.join(available)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
coverage={
 'requiredSources':[str(p.relative_to(root)) for p in source_files],
 'currentChineseSourceCharacters':len(all_cjk),'chineseMissing':missing_chinese,
 'coveredCharacters':len(out_cmap),'validatedOutlineCharacters':len(available),
 'outlineMismatch':outline_mismatch,'advanceWidthMismatch':width_mismatch,
 'copyrightAndLicenseNameRecordsUnchanged':True,
 'optionalSymbolFallback':[{'character':c,'codepoint':f'U+{ord(c):04X}'} for c in fallback],
 'fallbackPolicy':'Only upstream-absent punctuation/arrows use existing system fallback. All current Chinese source characters are present in the selected font.',
}
metadata={
 'name':'抖音美好体 Bold','family':family,'style':'normal','cssWeight':700,'fontSynthesis':'none',
 'approval':{'evidence':'用户在 V4 验收页选择 A：抖音美好体 Bold；选定截图开启立体厚度。','date':'2026-09-25'},
 'source':'https://github.com/bytedance/fonts','sourceCommit':'327565b61501d7a6d4902ed6ce417a7bd2ae54e6',
 'license':'SIL Open Font License 1.1','licenseSource':'https://github.com/bytedance/fonts/blob/main/DouyinSans/OFL.txt',
 'copyright':copyrights,
 'original':{'path':str(source.relative_to(root)),'version':'1.01','os2Weight':original_weight,'styleName':'Bold','bytes':source.stat().st_size,'sha256':sha(source)},
 'derivative':{'file':output.name,'fontUrl':'/fonts/orbital-forge/'+output.name,'family':family,'cssWeight':700,'os2Weight':verified['OS/2'].usWeightClass,'characters':len(out_cmap),'glyphs':len(verified.getGlyphOrder()),'bytes':output.stat().st_size,'sha256':sha(output),'renamed':True},
 'weightNote':'Upstream names its sole design Bold but its original OS/2 usWeightClass is 400. That metadata and the real outlines are preserved. CSS maps this supplied face explicitly to 700; font-synthesis:none prevents browser emboldening. This is not a native 700 metadata claim or synthesized 900.',
 'removedTables':removed,
 'modifications':'Renamed family/full/PostScript/unique/style records, selected current-site character subset, WOFF2 conversion, removal of malformed optional upstream GSUB. No outline or advance-width changes. Original OS/2 weight, copyright and license records preserved. Depth remains CSS text-shadow.',
 'coverage':coverage,
 'sourceFiles':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in source_files],
 'licenseFile':{'file':'OFL.txt','sha256':sha(output_dir/'OFL.txt')},
}
(output_dir/'SOURCE.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
(output_dir/'NOTICE.txt').write_text('\n'.join(copyrights)+'\n\nAtelier Forge Display is a renamed current-site subset derivative of DouyinSans Bold 1.01.\nSource: '+metadata['source']+'\nLicense: SIL OFL 1.1; see OFL.txt.\n\n'+metadata['weightNote']+'\n\n'+metadata['modifications']+'\n')
report={'ok':True,'sourceFontSha256':sha(source),'outputFontSha256':sha(output),'outputPath':str(output.relative_to(root)),'bytes':output.stat().st_size,'coverage':coverage,'sourceFiles':metadata['sourceFiles'],'productionCssWeight':700,'originalOs2Weight':original_weight,'syntheticBold':False}
(root/'assets/font-candidates/v4/production-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(output.relative_to(root)),'bytes':output.stat().st_size,'coverage':coverage,'sha256':sha(output)},ensure_ascii=False,indent=2))
