from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset
import hashlib, json, shutil, subprocess

root=Path(__file__).resolve().parents[3]
base=root/'assets/font-candidates/v4'
required='创作空间 创造新的世界 欢迎来到我的 游戏美术 个人作品集 我的作品 关于我 联系我 开始探索 作品档案 想象有形 每个世界从这里开始 让想象变成可以探索的世界 姓名待补充 游戏岗位作品展示 未提供信息待补充'
text=required+''.join(chr(i) for i in range(32,127))+'，。；：！？、（）【】「」“”‘’《》—…·'
configs=[
 dict(id='forge',letter='A',name='抖音美好体 Bold',shortName='抖音美好体',family='Atelier Forge Display',weight=400,file='douyin-upstream/DouyinSans/DouyinSansBold.ttf',licenseFile='douyin-upstream/DouyinSans/OFL.txt',repo='douyin-upstream',source='https://github.com/bytedance/fonts',licenseSource='https://github.com/bytedance/fonts/blob/main/DouyinSans/OFL.txt',author='抖音品牌创意中心 / 北京字跳网络技术有限公司',tag='厚块切角 · 几何秩序',description='饱满的黑度、利落的切角，像游戏标题中的实体标牌。适合偏科幻、硬表面与场景方向。',kind='全新候选'),
 dict(id='playcut',letter='B',name='站酷快乐体',shortName='站酷快乐体',family='Atelier Playcut Display',weight=400,file='kuaile-upstream/fonts/ttf/ZCOOLKuaiLe-Regular.ttf',licenseFile='kuaile-upstream/OFL.txt',repo='kuaile-upstream',source='https://github.com/googlefonts/zcool-kuaile',licenseSource='https://github.com/googlefonts/zcool-kuaile/blob/main/OFL.txt',author='The ZCOOL KuaiLe Project Authors',tag='不规则切面 · 手作游戏感',description='不规则转折与剪纸般的块面，艺术感更直接。适合风格化、独立游戏与创意玩法方向。',kind='全新候选'),
 dict(id='bouncy',letter='C',name='荆南波波黑 Bold',shortName='荆南波波黑',family='Atelier Bouncy Display',weight=700,file='bobo-upstream/fonts/TTF/KNBobohei-Bold.ttf',licenseFile='bobo-upstream/OFL.txt',repo='bobo-upstream',source='https://github.com/maoken-fonts/KNBobohei',licenseSource='https://github.com/maoken-fonts/KNBobohei/blob/main/OFL.txt',author='荆南字坊 / Kingnam Type Foundry',tag='饱满波浪 · 卡通雕塑感',description='波浪形笔画和柔软转角，厚重但不机械。适合卡通、玩具感与休闲游戏美术方向。',kind='全新候选'),
 dict(id='slant',letter='D',name='得意黑',shortName='得意黑',family='Atelier Slant Display',weight=400,file='../v3/smiley/SmileySans-Oblique.ttf',licenseFile='../v3/smiley/LICENSE.txt',source='https://github.com/atelier-anchor/smiley-sans',licenseSource='https://github.com/atelier-anchor/smiley-sans/blob/v2.0.1/LICENSE',author='atelierAnchor 锚坞',tag='前倾窄体 · 动势标题',description='明显的前倾与紧凑节奏，擅长短标题。作为旧候选基准，对照新字体的厚度与个性。',kind='旧候选基准'),
]
public=root/'public/font-review-v4';public.mkdir(parents=True,exist_ok=True)
for c in configs:
 source=base/c['file'];f=TTFont(source);cm=f.getBestCmap()
 removed_tables=[]
 # The official Douyin v1.01 TTF has an invalid GSUB subtable offset. Its
 # ordinary cmap/glyf/hmtx are valid; drop only the malformed optional table.
 # This is a renamed OFL derivative, with the repair disclosed alongside it.
 if c['id']=='forge':
  try:f['GSUB']
  except Exception:
   del f['GSUB'];removed_tables.append('GSUB: invalid upstream lookup/subtable offset')
 original_outlines={ch:list(f['glyf'][cm[ord(ch)]].getCoordinates(f['glyf'])[0]) for ch in set(required) if not ch.isspace()}
 missing=sorted({ch for ch in required if not ch.isspace() and ord(ch) not in cm});assert not missing,(c['id'],missing)
 copyrights=sorted({n.toUnicode() for n in f['name'].names if n.nameID==0})
 version=sorted({n.toUnicode() for n in f['name'].names if n.nameID==5})
 original_weight=f['OS/2'].usWeightClass
 options=subset.Options();options.name_IDs=['*'];options.name_languages=['*'];options.name_legacy=True
 options.notdef_glyph=True;options.notdef_outline=True;options.recommended_glyphs=True
 sub=subset.Subsetter(options=options);sub.populate(text=text);sub.subset(f)
 family=c['family'];ps=family.replace(' ','')
 for n in f['name'].names:
  if n.nameID in (1,4,6,16,18,21):n.string=(ps if n.nameID==6 else family).encode(n.getEncoding(),errors='replace')
  elif n.nameID==3:n.string=(ps+'-ReviewV4').encode(n.getEncoding(),errors='replace')
  elif n.nameID in (2,17,22):n.string='Regular'.encode(n.getEncoding(),errors='replace')
 if 'CFF ' in f:
  cff=f['CFF '].cff;cff.fontNames=[ps]
  for top in cff.topDictIndex:top.FullName=family;top.FamilyName=family
 folder=root/'public/fonts/review-v4'/c['id'];folder.mkdir(parents=True,exist_ok=True)
 output=folder/'display.woff2';f.flavor='woff2';f.save(output)
 shutil.copyfile(base/c['licenseFile'],folder/'OFL.txt')
 (folder/'CHARACTERS.txt').write_text(''.join(sorted(set(text)))+'\n')
 modifications='Review-only character subset, WOFF2 conversion, renamed primary family/full/PostScript/unique names. Original glyph outlines and native weight are unchanged. All copyright and OFL information retained. Visual depth is CSS text-shadow only.'
 if removed_tables:modifications+=' Removed malformed upstream optional GSUB substitution table; normal cmap/glyph outlines/advance widths preserved.'
 notice='\n'.join(copyrights)+'\n\nOriginal design: '+c['name']+'\nReview derivative family: '+family+'\nSource: '+c['source']+'\n'+modifications+'\n'
 (folder/'NOTICE.txt').write_text(notice)
 c['fontUrl']='/fonts/review-v4/'+c['id']+'/display.woff2';c['licenseUrl']='/fonts/review-v4/'+c['id']+'/OFL.txt'
 c['fontBytes']=output.stat().st_size;c['version']=version;c['originalOs2Weight']=original_weight;c['requiredTextMissing']=[]
 c['reviewOnly']=True;c['modified']=True;c['modifications']=modifications;c['copyright']=copyrights
 verified=TTFont(output);out_cmap=verified.getBestCmap()
 assert all(original_outlines[ch]==list(verified['glyf'][out_cmap[ord(ch)]].getCoordinates(verified['glyf'])[0]) for ch in original_outlines)
 c['glyphCount']=len(out_cmap);c['removedTables']=removed_tables;c['requiredOutlinesUnchanged']=True
 c['commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base/c['repo'],text=True).strip() if c.get('repo') else 'official release v2.0.1'
 c['sha256']={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in [('source',source),('woff2',output),('license',folder/'OFL.txt')]}
 (folder/'SOURCE.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
 evidence=base/c['id'];evidence.mkdir(exist_ok=True)
 (evidence/'SOURCE.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
 print(c['name'],c['fontBytes'],c['glyphCount'])
(public/'candidates.json').write_text(json.dumps(configs,ensure_ascii=False,indent=2)+'\n')
shutil.copyfile(root/'renders/homepage-background-concept-v2/concept.png',public/'background-direction.png')
