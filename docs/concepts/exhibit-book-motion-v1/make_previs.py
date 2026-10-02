from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np
import math, json, subprocess, pathlib, sys
import imageio_ffmpeg
ROOT=pathlib.Path(__file__).resolve().parents[3]
OUT=pathlib.Path(__file__).resolve().parent
W,H,FPS,DURATION=1280,720,30,32
FF=imageio_ffmpeg.get_ffmpeg_exe()
FONT='/System/Library/Fonts/STHeiti Medium.ttc'
FONTLIGHT='/System/Library/Fonts/STHeiti Light.ttc'
NAVY=(20,35,43); PAPER=(242,234,216); ORANGE=(235,153,77); INK=(31,48,56)
fonts={}
def ft(n,bold=True):
    key=(n,bold)
    if key not in fonts: fonts[key]=ImageFont.truetype(FONT if bold else FONTLIGHT,n)
    return fonts[key]
def clamp(x): return max(0,min(1,x))
def ease(x): x=clamp(x); return x*x*x*(10+x*(-15+6*x))
def phase(t,a,b): return ease((t-a)/(b-a))
def lerp(a,b,p): return a+(b-a)*p
def mixquad(a,b,p): return [(lerp(x,u,p),lerp(y,v,p)) for (x,y),(u,v) in zip(a,b)]
def text(im,xy,s,size=22,fill=INK,bold=True): ImageDraw.Draw(im).text(xy,s,font=ft(size,bold),fill=fill)
def wrap(s,font,width):
    out=[]; line=''
    for c in s:
        if font.getlength(line+c)>width: out.append(line);line=c
        else:line+=c
    if line:out.append(line)
    return out

def project(src,quad,size=(W,H)):
    # Inverse homography for an actual hinged plane, no image crossfade in page turns.
    dst=np.array(quad,dtype=float); sw,sh=src.size
    origin=[(0,0),(sw,0),(sw,sh),(0,sh)]
    A=[];B=[]
    for (x,y),(u,v) in zip(dst,origin):
        A.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]])
        B.extend([u,v])
    try: co=np.linalg.solve(np.array(A),np.array(B))
    except np.linalg.LinAlgError:return Image.new('RGBA',size)
    return src.convert('RGBA').transform(size,Image.Transform.PERSPECTIVE,co,Image.Resampling.BICUBIC)

def overlay(im, layer, alpha=1):
    if alpha<.999: layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:int(a*clamp(alpha))))
    im.alpha_composite(layer)

def view(src, zoom, center, base=.8):
    scale=base*zoom
    coeff=(1/scale,0,center[0]-W/(2*scale),0,1/scale,center[1]-H/(2*scale))
    return src.transform((W,H),Image.Transform.AFFINE,coeff,Image.Resampling.BICUBIC,fillcolor=(7,16,23)).convert('RGBA')
def coord(p,zoom,center,base=.8):return ((p[0]-center[0])*base*zoom+W/2,(p[1]-center[1])*base*zoom+H/2)
def qmap(q,z,c):return [coord(p,z,c) for p in q]

def shade(im,amount):
    if amount:overlay(im,Image.new('RGBA',(W,H),(6,13,20,int(255*amount))))
def pointer(im,p,click=0):
    x,y=p;d=ImageDraw.Draw(im)
    if click>0:
        r=10+22*click;d.ellipse((x-r,y-r,x+r,y+r),outline=(*ORANGE,int(230*(1-click))),width=3)
    d.polygon([(x,y),(x+3,y+27),(x+10,y+21),(x+17,y+32),(x+23,y+28),(x+16,y+17),(x+26,y+15)],fill=(255,246,225),outline=NAVY,width=2)
def callout(im,p,label,alpha=1):
    lay=Image.new('RGBA',(W,H));d=ImageDraw.Draw(lay);x,y=p
    d.ellipse((x-18,y-18,x+18,y+18),outline=ORANGE,width=2)
    d.line([(x+19,y-5),(x+70,y-52),(x+215,y-52)],fill=ORANGE,width=2)
    d.rounded_rectangle((x+63,y-88,x+249,y-47),10,fill=(*NAVY,235))
    text(lay,(x+78,y-80),label,18,PAPER)
    overlay(im,lay,alpha)

def chrome(im,t,chapter,caption):
    lay=Image.new('RGBA',(W,H));d=ImageDraw.Draw(lay)
    d.rounded_rectangle((26,22,432,64),11,fill=(13,26,35,235))
    text(lay,(43,33),chapter,18,PAPER)
    d.rounded_rectangle((958,22,1254,64),11,fill=(13,26,35,235))
    text(lay,(977,34),'动效预演 · 场景渲染合成示意',16,(205,214,213))
    width=ft(23).getlength(caption)+72
    x=(W-width)/2
    d.rounded_rectangle((x,642,x+width,696),14,fill=(13,26,35,242))
    d.rounded_rectangle((x+20,659,x+24,680),2,fill=ORANGE)
    text(lay,(x+38,657),caption,23,PAPER)
    d.line((0,718,W*t/DURATION,718),fill=ORANGE,width=3)
    overlay(im,lay)

GALLERY=Image.open(ROOT/'renders/works-gallery-v5/day-wide.png').convert('RGB')
ABOUT=Image.open(ROOT/'renders/about-atelier-v3-architecture-v2/hero.png').convert('RGB')
POSTER=Image.open(ROOT/'public/media/works/sugar-shell-glutton/poster.webp').convert('RGB')
COPY=json.loads((OUT/'resume-preview-copy.json').read_text())['pages']
ARTQ=[(586,385),(645,399),(646,491),(590,477)]
BOOKQ=[(817,483),(894,467),(980,493),(899,516)]
BOOKQ=[(898+(x-898)*1.45,491+(y-491)*1.45) for x,y in BOOKQ]
# Same first-project identity as the website, composited on its existing frame for the previs.
cover=Image.new('RGB',(250,380),PAPER);cover.paste(POSTER.resize((222,125)),(14,82))
text(cover,(16,20),'01 / PLAYABLE',18)
text(cover,(17,232),'糖壳暴食兽',27)
text(cover,(17,280),'玩法 · 成长 · 迭代',17)
GALLERY=GALLERY.convert('RGBA');GALLERY.alpha_composite(project(cover,ARTQ,GALLERY.size));GALLERY=GALLERY.convert('RGB')

PANEL_SIZE=(1020,480);PANEL_Q=[(130,133),(1150,133),(1150,613),(130,613)]
def panel(frame):
    im=Image.new('RGBA',PANEL_SIZE);d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,1019,479),18,fill=(*PAPER,255),outline=(162,145,114),width=2)
    d.rounded_rectangle((0,0,10,479),5,fill=ORANGE)
    text(im,(30,20),'01  /  作品档案',15,(119,103,78))
    text(im,(30,48),'糖壳暴食兽',31)
    text(im,(30,93),'开发中原型 · Vibe Coding 实践',16,(104,111,106))
    d.ellipse((971,21,997,47),fill=(225,216,198));text(im,(976,18),'×',24)
    im.paste(frame.resize((590,332),Image.Resampling.LANCZOS),(30,131))
    text(im,(650,133),'从玩法想法到可玩验证',24)
    entries=[('01  玩法循环','战斗、成长与选择形成反馈'),('02  策划迭代','5 阶进化 · 三选一 · 道具叠加'),('03  内容表达','用实机视频说明规则与亮点')]
    for i,(head,body) in enumerate(entries):
        y=188+i*82
        d.line((650,y-11,980,y-11),fill=(204,192,169),width=1)
        text(im,(650,y),head,19)
        text(im,(650,y+30),body,17,(105,108,99),False)
    text(im,(650,443),'项目贡献与过程材料可继续展开',15,(134,114,88))
    return im

PAGE_W,PAGE_H=454,428

def page_content(idx):
    im=Image.new('RGBA',(PAGE_W,PAGE_H),(*PAPER,255));d=ImageDraw.Draw(im)
    # Fine paper and spine shading, static texture and readable content.
    for x in range(PAGE_W):
        v=int(242-11*math.exp(-min(x,PAGE_W-x)/15))
        d.line((x,0,x,PAGE_H),fill=(v,v-8,v-25))
    text(im,(32,25),f'WCY  /  {idx+1:02d}',14,(145,109,66))
    text(im,(32,68),COPY[idx]['title'],31)
    d.line((32,116,420,116),fill=(171,135,81),width=2)
    for i,s in enumerate(COPY[idx]['items']):
        y=142+i*56
        d.ellipse((33,y+8,38,y+13),fill=(165,116,57))
        lines=wrap(s,ft(18),354)
        for k,ln in enumerate(lines):text(im,(49,y+k*24),ln,18,INK,False)
    d.line((32,390,420,390),fill=(198,181,151))
    text(im,(32,403),'GAME DESIGN + CONTENT OPERATIONS',11,(139,121,91))
    return im
PAGES=[page_content(i) for i in range(4)]

def book(pflip=0,opening=1):
    # Book returns a consistent 960×456 object. Opening rotates left leaf around spine.
    im=Image.new('RGBA',(960,456));d=ImageDraw.Draw(im)
    base_left=480-454*max(0,-math.cos(math.pi*opening))
    d.rounded_rectangle((base_left-9,10,951,452),10,fill=(79,52,33),outline=(158,115,61),width=3)
    for off in [6,4,2]:d.rounded_rectangle((base_left-6,12+off,940,442+off),3,fill=(205+off,189+off,161+off))
    left=[(26,13),(480,13),(480,441),(26,441)];right=[(480,13),(934,13),(934,441),(480,441)]
    if opening<.999:
        current_left=2 if pflip>.5 else 0
        current_right=current_left+1
        overlay(im,project(PAGES[current_right],right,im.size))
        # Navy/gold hardback opens counter-clockwise about the book's spine.
        cover=Image.new('RGBA',(454,428),(*NAVY,255));dd=ImageDraw.Draw(cover)
        dd.rectangle((24,24,430,404),outline=(191,151,91),width=2)
        text(cover,(58,90),'王丞业',42,PAPER);text(cover,(58,163),'个人能力档案',26,PAPER)
        text(cover,(58,330),'策划 / 运营',20,(193,156,103))
        theta=opening*math.pi;w=454*abs(math.cos(theta));lift=45*math.sin(theta)
        if opening<.5:
            q=[(480,13),(480+w,13-lift),(480+w,441+lift),(480,441)];src=cover
        else:q=[(480-w,13-lift),(480,13),(480,441),(480-w,441+lift)];src=PAGES[current_left]
        if w>1:overlay(im,project(src,q,im.size))
        if opening>.5:overlay(im,project(PAGES[current_right],right,im.size))
    else:
        overlay(im,project(PAGES[0] if pflip<1 else PAGES[2],left,im.size))
        overlay(im,project(PAGES[1] if pflip<=0 else PAGES[3],right,im.size))
        if 0<pflip<1:
            theta=pflip*math.pi;w=454*abs(math.cos(theta));lift=43*math.sin(theta)
            if pflip<.5:q=[(480,13),(480+w,13-lift),(480+w,441+lift),(480,441)];src=PAGES[1]
            else:q=[(480-w,13-lift),(480,13),(480,441),(480-w,441+lift)];src=PAGES[2]
            if w>1:
                src=ImageEnhance.Brightness(src).enhance(1-.15*math.sin(theta))
                overlay(im,project(src,q,im.size))
    d=ImageDraw.Draw(im);d.line((480,14,480,440),fill=(144,116,77,165),width=2)
    return im

# Enlarge the desk book in the concept before the click, keeping the underlying scene untouched.
desk_cover=book(0,0).crop((468,0,960,456))
ABOUT=ABOUT.convert('RGBA');ABOUT.alpha_composite(project(desk_cover,BOOKQ,ABOUT.size));ABOUT=ABOUT.convert('RGB')

# Predecode real silent gameplay excerpt; the visible player is actually moving.
FRAME_DIR=OUT/'game-frames';FRAME_DIR.mkdir(exist_ok=True)
if not (FRAME_DIR/'0300.jpg').exists():
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-ss','8','-i',str(ROOT/'public/media/works/sugar-shell-glutton/demo-1080p.mp4'),'-t','10','-vf','fps=30,scale=590:332','-q:v','4',str(FRAME_DIR/'%04d.jpg')],check=True)
GAME=[Image.open(p).convert('RGB') for p in sorted(FRAME_DIR.glob('*.jpg'))]
BOOK_DEST=[(160,147),(1120,147),(1120,603),(160,603)]

def make_frame(t):
    if t<13.4:
        push=phase(t,1.5,3.4)*(1-phase(t,10.9,12.7))
        z=lerp(1,1.52,push);c=(lerp(800,640,push),lerp(550,465,push))
        im=view(GALLERY,z,c)
        anchor=qmap(ARTQ,z,c)
        if t<1.7:
            p=coord((619,441),z,c);callout(im,p,'第 1 展架',1-phase(t,1.4,1.7));pointer(im,(p[0]+8,p[1]+18),clamp((t-.95)/.5) if t>.95 else 0)
        unfold=phase(t,3.15,4.65)*(1-phase(t,9.8,11.1))
        if unfold>0:
            shade(im,.18*unfold)
            fr=GAME[int(max(0,t-4.5)*FPS)%len(GAME)]
            q=mixquad(anchor,PANEL_Q,unfold)
            shadow=Image.new('RGBA',(W,H));dd=ImageDraw.Draw(shadow)
            dd.polygon([(x+3,y+12) for x,y in q],fill=(0,0,0,110));shadow=shadow.filter(ImageFilter.GaussianBlur(14))
            overlay(im,shadow,unfold);overlay(im,project(panel(fr),q))
            if 8.8<t<9.8:pointer(im,(1126,172),clamp((t-9.25)/.4))
        if t<1.5:caption='点击展架，打开这件作品'
        elif t<3.4:caption='镜头先向前推进，聚焦第一个展架'
        elif t<4.65:caption='展示内容从展架展开，保留四周场景'
        elif t<9.8:caption='视频播放 + 图文说明，不占满整个屏幕'
        else:caption='关闭后收回展架，镜头回到原位'
        chrome(im,t,'01  /  长廊作品 · 推进与展开',caption)
        return im
    # Book segment: initial source is same on-desk geometry, enlargement demonstrated by lift.
    bt=t-13.4
    push=phase(bt,1.4,3.3)*(1-phase(bt,15.1,16.8))
    z=lerp(1,1.65,push);c=(lerp(800,905,push),lerp(500,490,push))
    im=view(ABOUT,z,c)
    if bt<1.5:
        p=coord((899,490),z,c);callout(im,p,'桌面简历书');pointer(im,(p[0]+13,p[1]+12),clamp((bt-.85)/.45) if bt>.85 else 0)
    rise=phase(bt,3.1,4.4)*(1-phase(bt,13.9,15.4))
    if rise>0:
        shade(im,.23*rise)
        q=mixquad(qmap(BOOKQ,z,c),BOOK_DEST,rise)
        flip=phase(bt,8.5,9.7)
        # Opening overlaps the end of camera push; close before folding back to desk.
        opening=phase(bt,3.5,5.15)*(1-phase(bt,13.2,14.25))
        obj=book(flip,opening)
        shadow=Image.new('RGBA',(W,H));ImageDraw.Draw(shadow).polygon([(x,y+12) for x,y in q],fill=(0,0,0,135));shadow=shadow.filter(ImageFilter.GaussianBlur(18))
        overlay(im,shadow,rise);overlay(im,project(obj,q))
        if 7.8<bt<9.15:pointer(im,(1090,550),clamp((bt-8.35)/.35))
    if bt<1.4:caption='放大桌上的书，让它成为清晰的个人介绍入口'
    elif bt<3.3:caption='点击书本，镜头沿桌面向前推进'
    elif bt<5.15:caption='书本抬起、放大并打开，场景仍留在背后'
    elif bt<8.5:caption='第一组书页：个人概览 + 游戏策划能力'
    elif bt<9.7:caption='点击页角，纸张绕书脊翻动'
    elif bt<13.2:caption='第二组书页：游戏运营能力 + 项目与联系'
    elif bt<16.8:caption='合上书本回到桌面，恢复场景浏览'
    else:caption='先验收动作与节奏，通过后再制作正式交互'
    chrome(im,t,'02  /  关于我 · 简历书翻页',caption)
    if t<14.0:
        previous=make_frame(13.39)
        im=Image.blend(previous,im,phase(t,13.4,14.0))
    return im

if '--stills' in sys.argv:
    for sec in [0.8,2.7,4.0,6,10.5,14.2,16,18.8,20.5,22.5,24.3,28.7]:
        make_frame(sec).convert('RGB').save(OUT/f'frame-{sec:.1f}.jpg',quality=94)
    thumbs=[]
    for sec in [0.8,2.7,4.0,6,14.2,16,18.8,20.5,22.5,24.3,28.7]:
        ti=make_frame(sec).convert('RGB').resize((480,270));d=ImageDraw.Draw(ti);d.rectangle((0,0,65,23),fill=NAVY);d.text((6,3),f'{sec:.1f}s',font=ft(16),fill=PAPER);thumbs.append(ti)
    sheet=Image.new('RGB',(1440,1080),NAVY)
    for i,ti in enumerate(thumbs):sheet.paste(ti,((i%3)*480,(i//3)*270))
    sheet.save(OUT/'contact-sheet.jpg',quality=94)
else:
    path=OUT/'motion-previs-v1.mp4'
    enc=subprocess.Popen([FF,'-y','-hide_banner','-loglevel','warning','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],stdin=subprocess.PIPE)
    for i in range(DURATION*FPS):
        frame=make_frame(i/FPS).convert('RGB');enc.stdin.write(frame.tobytes())
        if i%(FPS*4)==0:print(f'Rendered {i/FPS:.0f}/{DURATION}s',flush=True)
    enc.stdin.close()
    if enc.wait()!=0:raise RuntimeError('ffmpeg encode failed')
    make_frame(6).convert('RGB').save(OUT/'poster.jpg',quality=95)
    print(path,flush=True)
