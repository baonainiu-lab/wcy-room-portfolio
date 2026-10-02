from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset
import hashlib,json,shutil
root=Path('/Users/a90/Documents/ChatGPT/个人网站/room-portfolio')
base=root/'assets/font-candidates/v3'
required='创作空间 个人作品集 作品 关于 联系 白天 夜晚 拖动旋转 点击探索 在这里，记录创作与想象 0123456789 Aa Bb Cc'
text=required+''.join(chr(i) for i in range(32,127))+'，。；：！？、（）【】「」“”‘’《》—…·'
for p in [root/'index.html',*list((root/'src').glob('*.js'))]:
 text+=''.join(c for c in p.read_text() if 0x3000<=ord(c)<=0x9fff)
configs=[dict(slug='chill-tanhei',file='ChillInorganic_WideMedium.otf',family='Atelier Reverse Display',name='寒蝉无机体·宽体',weight=500,style='逆反差美术字；横笔厚、竖笔细，宽展字面，带雕刻与展览标题感。',source='https://github.com/Warren2060/ChillTanHei',licenseSource='https://github.com/Warren2060/ChillTanHei/blob/main/License',download='https://github.com/Warren2060/ChillTanHei/releases/download/v1.00/ChillTanHei_v1.00.zip'),dict(slug='chill-rounded-heavy',file='ChillRoundGothic_Heavy.ttf',family='Atelier Rounded Display',name='寒蝉圆黑体 Heavy',weight=900,style='原生900极粗圆角黑体；笔画厚实，端点圆润，适合与房间的圆角金属和暖光搭配。',source='https://github.com/Warren2060/ChillRoundGothic',licenseSource='https://github.com/Warren2060/ChillRoundGothic/blob/main/License.txt',download='https://raw.githubusercontent.com/Warren2060/ChillRoundGothic/main/ttf/ChillRoundGothic_Heavy.ttf')]
for c in configs:
 src=base/c['slug']/c['file']
 if not src.exists():continue
 f=TTFont(src)
 names={r.toUnicode() for r in f['name'].names if r.nameID==0}
 assert all(ord(ch) in f.getBestCmap() for ch in required if not ch.isspace())
 opts=subset.Options()
 opts.name_IDs=['*'];opts.name_languages=['*'];opts.name_legacy=True
 opts.notdef_glyph=True;opts.notdef_outline=True;opts.recommended_glyphs=True
 sub=subset.Subsetter(options=opts);sub.populate(text=text);sub.subset(f)
 family=c['family'];ps=family.replace(' ','')
 # Preserve all copyright and license records; give derivative distinct primary names.
 for r in f['name'].names:
  if r.nameID in (1,4,6,16,18,21):
   val=ps if r.nameID==6 else family
   r.string=val.encode(r.getEncoding(),errors='replace')
  elif r.nameID==3:r.string=(ps+'-review-v3').encode(r.getEncoding(),errors='replace')
  elif r.nameID in (2,17,22):r.string='Regular'.encode(r.getEncoding(),errors='replace')
 if 'CFF ' in f:
  cff=f['CFF '].cff;cff.fontNames=[ps]
  for top in cff.topDictIndex:
   top.FullName=family;top.FamilyName=family
 public=root/'public/fonts/review-v3'/c['slug'];public.mkdir(parents=True,exist_ok=True)
 out=public/'display.woff2';f.flavor='woff2';f.save(out)
 shutil.copyfile(src.parent/'OFL.txt',public/'OFL.txt')
 check=TTFont(out);missing=sorted(set(c for c in text if not c.isspace() and ord(c) not in check.getBestCmap()))
 info={**c,'fontUrl':'/fonts/review-v3/'+c['slug']+'/display.woff2','fontPath':str(out.relative_to(root)),'sourcePath':str(src.relative_to(root)),'license':'SIL Open Font License 1.1','licenseUrl':'/fonts/review-v3/'+c['slug']+'/OFL.txt','copyright':sorted(names),'reviewOnly':True,'originalOs2Weight':f['OS/2'].usWeightClass,'version':next((r.toUnicode() for r in f['name'].names if r.nameID==5),'unknown'),'subsetChars':len(check.getBestCmap()),'requiredTextMissing':[],'extraTextMissing':missing,'sha256':{'source':hashlib.sha256(src.read_bytes()).hexdigest(),'woff2':hashlib.sha256(out.read_bytes()).hexdigest(),'license':hashlib.sha256((public/'OFL.txt').read_bytes()).hexdigest()},'bytes':{'source':src.stat().st_size,'woff2':out.stat().st_size},'modifications':'Review-only character subset; converted to WOFF2; renamed primary family/PostScript/unique names. Outlines and native weight preserved. OFL retained in font and adjacent file.'}
 (src.parent/'SOURCE.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
 (public/'NOTICE.txt').write_text('\n'.join(sorted(names))+'\n\nReview derivative family: '+family+'\nSource: '+c['source']+'\n'+info['modifications']+'\n')
 print(json.dumps(info,ensure_ascii=False,indent=2))
