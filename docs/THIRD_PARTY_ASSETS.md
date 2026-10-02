# 第三方素材核查台账

## About Atelier V3 档案工坊 · 2026-09-30

用户通过 A 概念后，新建 `assets/blender/about-atelier-v3.blend`。场景几何与原创陈设在 Blender 制作；未加入网站运行时。

真实贴图采用 Poly Haven Walnut Veneer（Jenelle van Heerden）、Brown Leather（Rob Tuytel）、Hessian 230（colormass / Rico Cilliers），以及 ambientCG Terrazzo001（Lennart Demes）；湖景 HDRI 为 Poly Haven Lake Pier（Alexander Scholten）。以上原始资产均核实为 CC0 1.0。完整作者/官方页/下载地址/许可原文/哈希见 [材质来源](../assets/textures/about-atelier-v3/README.md) 和 [湖景清单](../assets/textures/about-atelier-v3/landscape/manifest.json)。原始图片不改写，节点调色单独保存，实际使用图片已打包进源文件。

文字使用项目原版 DouyinSans Bold，继续保留 SIL OFL 1.1，不归入模板 MIT。关于用户的奖项、技能与联系方式仍待补充。本轮没有部署或发布，离线源文件不代表网页资产或性能验收通过。见 [本版说明](ABOUT_ATELIER_V3.md)。

## About Nexus V2 独立模型 · 2026-09-29

`assets/blender/about-nexus-v2.blend` 为本轮新建的圆形档案工作站。建筑底盘、机械档案盘、奖项占位雕塑、收藏舱、技能转盘、联系终端及程序材质均在 Blender 中原创制作，没有使用第三方模型、照片或 HDRI。模型目前只供外观验收，未加入网站运行时。

文字使用未修改的项目现有 `DouyinSansBold.ttf`，版权为 2023 Beijing Zitiao Network Technology Co. Ltd.，适用 SIL Open Font License 1.1。字体及原文许可已随 `.blend` 打包（`FONT_LICENSE_OFL.txt` 文本块）；字体不归入模板 MIT。源文件及待验收状态见 [ABOUT_NEXUS_V2.md](ABOUT_NEXUS_V2.md)。

核查日期：2026-09-21。基准提交：`2a17ff26c980f6e33edfaea9300381198365a49a`。

本表是文件来源与授权证据记录；“待核实”不等于已经证明侵权，也不等于已获准复用。网页许可信息还需对应到最终使用的具体文件、版本与用途。

## 模板代码

根目录 `LICENSE.md` 为 MIT，版权声明为 **Copyright (c) 2025 Andrew Woan**，已原样保留。上游 README 已存为 `UPSTREAM_README.md`，保留致谢线索。

仓库代码许可不自动覆盖第三方字体、音频、壁纸、角色图或购买的材质。素材核实或替换完成前，不把当前模板基线作为新站发布成果。

## 素材清单

下表保留最初模板基线的审查记录，文件路径是当时相对项目根目录的位置；它不是当前网站的素材使用清单。本次试接入已改用新模型与原创场景素材，旧模板资源退出运行时使用。`blender files/` 仅存在于相邻上游参考目录，未复制到新项目。

| 文件 / 类别 | 来源与当前证据 | 状态与后续处置 |
| --- | --- | --- |
| `public/models/Room_Portfolio.glb`、`public/textures/room/{day,night}/*`；上游 Blender 工程 | [README](UPSTREAM_README.md) 致谢 [Denis Wipart](https://wipart.artstation.com/store)，仅称原作者本人有商用许可；未见具体商品和可再分发凭证。 | 待核实；新房间自行建模、制作材质、重新烘焙，替换整套旧房间资产。 |
| `public/fonts/ShiftyNotes-Regular.{woff,woff2}` | [作者发布页](https://www.fontspace.com/shifty-notes-font-f89941) 标记 Personal Use Free，商业使用需另行许可。 | 不直接复用；优先替换成许可明确且可网页嵌入的字体。 |
| `public/fonts/MotleyForces-Regular.{woff,woff2}` | [作者发布页](https://www.fontspace.com/motley-forces-font-f87817) 标记 Freeware，并明确允许商业项目；仓库无独立字体许可文件。 | 基本使用许可有依据；保留时补存许可说明，并核实 WOFF 来源/转换。 |
| `public/audio/music/cosmic_candy.ogg` | 上游页面标为 Daystar Project 的 Cosmic Star Candy；[视频来源](https://www.youtube.com/watch?v=eq3C1Uwz6YU)，未取得完整适用许可条件。 | 待核实；标题中的 Royalty Free 不作为完整授权证明，优先替换。 |
| `public/audio/sfx/click/bubble.ogg` | README 仅给 Uppbeat 分类链接，缺精确素材页与下载凭证；[官方许可](https://uppbeat.io/uppbeat-basic-license) 有使用和分发条件。 | 待核实；优先自制合成点击音效，保留触发方式。 |
| `public/audio/sfx/piano/Key_1.ogg` 至 `Key_24.ogg` | [素材页](https://pixabay.com/sound-effects/musical-all-88-keys-on-a-piano-playing-fast-free-high-quality-sound-effects-71279/) 标示 Pixabay Content License；[许可摘要](https://pixabay.com/service/license-summary/) 包含独立分发限制。 | 有来源线索；裁切来源与最终网站/公开仓库分发方式待复核，或改用自制合成音色。 |
| 原房间壁纸、海报、角色图片 | README 列 Cat、Peach Cat/Panda、Anya；上游 `blender files/images/` 还含 Kirby、BTS 等图像，未见逐项授权，未确认与烘焙贴图映射。 | 全部替换为用户自有或新创作图像；不能通过沿用旧烘焙图绕过替换。 |
| `public/textures/video/Screen.mp4` | 被 main.js 实际加载；未找到单独来源及许可。 | 待核实；替换为用户作品视频或待补充屏幕。 |
| `public/images/{profile_pic,community,computer,piano}.webp`、`public/media/og-image.webp`、深浅 favicon | 原作者身份/作品展示素材，无独立来源记录。 | 按任务要求全部替换；资料缺失使用“待补充”。 |
| 上游 `blender files/images/kiara_1_dawn_4k.hdr` | 文件名对应 [Poly Haven Kiara 1 Dawn](https://polyhaven.com/a/kiara_1_dawn)，作者 Greg Zaal，来源页标记 CC0。 | 来源许可已核查；未复制，若决定使用需核实具体文件对应关系。 |
| `public/textures/skybox/*.webp`、`public/shaders/perlin.png`；上游 `superclean.png` | 未找到精确来源；不能从名称推断 skybox 一定来自上述 HDRI。 | 待核实；重做或补来源证据。 |
| `index.html` 内联 SVG 图标 | README 仅指向 SVG Repo 首页；[平台许可说明](https://www.svgrepo.com/page/licensing) 存在多种许可。 | 缺逐个图标页；优先替换为自制简单图形或统一的明确许可图标集。 |
| `public/draco/*` 与 `public/draco/gltf/*` | 自带 README 指向 Apache 2.0；模板未附完整 Draco LICENSE。[官方许可](https://github.com/google/draco/blob/main/LICENSE) | 当前新 GLB 不使用 Draco，旧解码文件不随本次网页预览分发。以后启用时再补齐对应版本 LICENSE/NOTICE。 |

## 依赖许可

原模板 npm 锁文件中的 GSAP 3.12.7 标注 GreenSock Standard “no charge” license，不能将整个依赖树统称 MIT。本次本地安装改由 `pnpm-lock.yaml` 记录，实际运行时依赖与许可存档如下：

| 依赖 | 本地版本 | 许可证据 |
| --- | --- | --- |
| Three.js（包括 GLTFLoader 和控件依赖） | 0.172.0 | 包内 MIT 文本原样保存于 [three-0.172.0-LICENSE.txt](licenses/three-0.172.0-LICENSE.txt)。 |
| GSAP | 3.15.0 | 包内声明为 Standard “no charge” license；[包内声明](licenses/gsap-3.15.0-NOTICE.txt) 与 [官方条款文本存档](licenses/gsap-standard-license-2026-09-21.txt) 已保存。官方来源为 [GSAP Standard License](https://gsap.com/community/standard-license/)，2026-09-21 检索，页面标明生效日期 2025-04-30、最后修改日期 2025-05-30。 |

这里记录具体依赖声明和来源，不把 GSAP 改标为 MIT，也不将本地预览视为整个依赖树的发布审查完成。构建工具与未使用的模板依赖仍按锁文件保留；最终发布前应按实际产物保留所需声明。

## 后续每项素材需记录

具体文件和哈希、作者/原始链接、许可文本及版本、核查日期、允许用途、是否有署名要求、是否允许公开仓库分发、替换或保留结果。上表保留历史来源问题；当前预览使用项见下节。此台账不构成用户的发布授权。

## 当前 V13 夜间暖光资产

V13 已接入本地网站，新增桌下、窗下的暖光与既有灯具调整均为本项目在 Blender 中制作，无新增第三方模型、材质或灯光环境。夜间八图集已重烘，几何、UV、法线、索引及层级变换精确继承 V12，8 张日间图集和日景窗图逐字节保留，夜景窗图亦未改；证据见[交付报告](../assets/blender/night-warm-v13-delivery.json)、[连续性验证](../renders/night-warm-v13-continuity-check.json)与[源日景核验](../assets/blender/source-day-v13-verification.json)。

完整源 `assets/blender/orbital-atelier-v13.blend` 为 73,860,523 字节，SHA-256 `2469222a77fc326d34223785a15675cf1abf65ecdf6c9297ca2619d9d9f16d17`。当前 GLB `public/models/orbital-atelier-v13.glb` 为 46,178,184 字节，SHA-256 `44178b2372dfb4978da24fb6910c0d279bc353a9ed4936656fb52d45e18824f9`；373,203 三角形、100 个绘制图元、10 张内嵌图像，37 / 93 室内资产统计与 2 个外部 ID 校验通过。

V13 初次接入时 UI V2 采用下方历史字体条目记录的本地 Noto Serif SC 派生子集，按 OFL 1.1 单独分发；模板 MIT 与依赖声明保持。字体视口检查已通过，V13 整合后构建通过（20 个模块），夜景目视与[性能采样](../renders/performance-night-warm-v13.json)已记录，昼夜切换、显示屏打开作品、Esc 关闭回归已通过；未证明稳定 120 FPS，最终视觉仍待用户验收，仅本地预览。

## 历史 V12 资产与概念状态

V12 在本项目原创 V11 源场景上修复建筑曲面、硬边 / 法线和倒角，并提升两终端与盆景的网页几何预算；没有引入第三方模型、图像或材质。源为 `assets/blender/orbital-atelier-v12.blend`，SHA-256 为 `9b7936dcebdb3974703c37772911d596b0a8a196743e99c9e757bf21a38d5b8c`；当前 GLB 为 `public/models/orbital-atelier-v12.glb`，46,378,804 字节，SHA-256 为 `a26569fd7a0a1e0e6c1e30c5409aa58fd021009704fdcacf49cef81f5ee45c10`。

图集 0、2 的日夜两态已实际重烘；1、3–7 通过包含角法线和平滑面标志的表面指纹验证后复用。`renders/asset-validation-v12.json` 通过，室内 37 根资产 / 93 ID 加 2 个外部 ID、10 张内嵌图像保留。UV 重分配 helper 未启用，详细取舍见 [V12 精度说明](MODEL_PRECISION_V12.md)。

V12 已接入本地网站，构建通过；日夜画面、指定镜头操作与交互已检查，并保存静置性能采样，实际范围见[预览检查](PREVIEW_CHECK.md)。用户尚未最终验收视觉，未证明稳定 120 FPS。用户随后明确授权“ui先按这个概念图设计吧”并要求继续，UI 概念已获准实现；新界面已接入，UI V1 最终构建通过（20 个模块），指定视口与交互的浏览器 QA 已完成，最终视觉仍待用户验收；详见[实现记录](UI_CONCEPT_V1_IMPLEMENTATION.md)及[浏览器证据](../renders/ui-v1-browser-check.json)。上述 V12 模型检查与性能证据早于新 UI 接入，不替代本轮 UI 验收。角色暂不接入。以下 V11 / V9 / V8 记录是历史来源证据，不能作为新 UI 已验收或 V12 稳定 120 FPS 的证明。

## 历史本地展示字体 · UI V2

本地 `public/fonts/orbital-editorial/orbital-editorial-sc-ui.woff2` 是 Noto Serif SC 的修改子集，派生名称为 `Orbital Editorial SC`，用于标题、导航、昼夜标签和物件名称。它按 SIL Open Font License 1.1 单独记录，不归入模板 MIT。

| 项目 | 当前证据 |
| --- | --- |
| 来源与派生过程 | [字体实现记录](UI_TYPOGRAPHY_V2.md)、[SOURCE.json](../public/fonts/orbital-editorial/SOURCE.json)；Google Fonts / Noto Serif SC，核查日期 2026-09-22 |
| 本地许可 | [原样 OFL.txt](../public/fonts/orbital-editorial/OFL.txt)，保留 `Copyright 2012 Google Inc. All Rights Reserved.` |
| 文件与子集 | 188,964 字节；497 字符 / 910 字形，变量字重范围 600–700；派生 family / PostScript 名已重命名 |
| SHA-256 | `e79e72d9ffe6beec7fc755bc3518bae5df6a1ec595bf2c4c9a671aaaf5b40004` |
| 分发说明 | 随字体保留版权与 OFL，字体及派生文件继续使用 OFL，不将字体单独出售，不以原作者名义为派生字体背书 |
| 运行时使用 | 浏览器读取本地 WOFF2，无 Google Fonts 网络请求；正文保留系统字体，新增子集外文字回退到系统宋体 |

UI V2 字体在 844 px 与 320 px 视口已检查，与 V13 灯光整合后的最终完整构建通过（20 个模块）；见字体实现记录中的实际范围。上方历史字体许可表保持原文；下方 V8“系统字体栈”描述只适用于当时版本。

## 历史 V11 资产与概念图


V10 墙体向外加厚、向上增高及墙脚承托已完成；V11 在同一原创源场景中修复窗角与墙顶、展示柜的交接。脚本为 `thicken_walls_v10.py`、`fix_window_junction_v11.py`，尺寸和检测证据保存在对应 JSON 报告；本轮未引入第三方模型或素材。

当时完整源工程为 `assets/blender/orbital-atelier-v11.blend`，SHA-256 为 `f60171543a8bf48c855e672a2055ced1dce2a178d0b1a47eefb0437ea240d785`。网页模型 `public/models/orbital-atelier-v11.glb` 为 45,278,140 字节，SHA-256 为 `271e01a78c53d45646d964890789c46d533bfb664b0b4121b7faaa1594b2b37b`；`renders/asset-validation-v11.json` 通过，室内 37 个根资产、93 个 ID 及 2 个外部 ID 保留。

建筑图集 0 的日夜两态已重烘；图集 1–7 经 `retained-uv-v11-verification.json` 证明几何及 UV 与 V10 精确一致后沿用。屏幕和城市日夜窗景均为本项目 Blender 渲染。夜间外部图集的线性曝光调整及程序背景压暗是网页显示参数，不新增外部素材。

UI 概念图在 V11 阶段生成，副本及批准记录位于 [ui-v1](concepts/ui-v1/README.md)。用户当时仅认可大方向并要求修改细节，开发曾暂停；随后已明确批准按图实现，当前进展见前文。概念图本身不是实机截图，也不代表图中新增背景建筑已建模或获准交付。角色试作仍不接入，个人资料继续标记待补充。

上述为 V11 阶段的记录；当前 V12 浏览器检查另见前文。V9 性能文件只作历史基线，不证明 V11 稳定 120 FPS。模板 MIT、依赖声明和本页历史素材证据原样保留，仅本地预览，无发布授权。

## 历史 V9 白天日光更新


2026-09-22 追加：V9 使用现有本项目几何与 UV，仅以 Blender 中新的真实太阳和天空设置重烘白天 8 组图集；无新增网页可见资产，也没有引入第三方模型、贴图或 HDRI。V8 GLB 与夜间图集保持原样，室内 37 个根资产、93 个稳定 ID 和 2 个外部环境 ID 不变。

`day_sunlight_v9.py` 设置真实 Sun `(7, 16, 12)`、强度 18、天空强度 0.16、角直径 0.526°；日景窗洞阴影射线透射、屋顶挡光代理与三根窗框投影代理是本项目自己的灯光制作手段。代理摄影机不可见且不导出为网页几何，其投影效果进入日间烘焙图。

实际 Blender 预览为 `renders/lighting-v9-day-blender.png`。`run_day_sunlight_v9.py` 已完成 `public/textures/lighting-v9/day-0.png` 至 `day-7.png`，并接入网页；日景窗图仍用 V8 原创城市渲染 `public/textures/lighting-v8/window-day.png`。`renders/asset-validation-v9.json` 校验通过，确认 V8 GLB 与全部 8 张夜间图集哈希未改。V9 完整可编辑工程已保存并重新打开核对，SHA-256 为 `4baa50f14c06ed7a696c960953675e9e27d2d667c701861fd27c693ed1ce7cd2`，见 `assets/blender/day-source-v9-report.json`；V9 网页日夜截图与本轮静置性能报告已留档，最终视觉仍待用户验收，未宣称稳定 120 FPS。

用户要求角色暂不接入；运行入口与交互已撤下，试作源码和资产作为待定资料保留，见 [角色方案状态](AVATAR_IMPLEMENTATION_PLAN.md)。本轮不将角色试作作为已确认的网站展示资产。模板 MIT 与上述第三方历史许可证据不变，仍仅本地预览。

## 已完成的 Blender 资产来源 · V8

2026-09-22 更新：V8 制作源为 `assets/blender/orbital-atelier-v8-interior.blend`，由本项目 V7 完整场景及 `build_warm_interior_v8.py` 新建的桌边遮光灯、窗下灯条、茶几阅读灯组成。几何、材质、灯光均在 Blender 中制作，新增内容未下载第三方模型、付费材质、字体或角色图像。完整可编辑日夜工程 `assets/blender/orbital-atelier-v8.blend` 已保存。

城市日景和夜景由 `render_window_states_v8.py` 对本项目原 ENV_CITY 三维场景分别设置并实际渲染；屏幕图形来源于本项目 SCREEN_ART 三维雕塑的实际渲染。日夜天空使用 Blender 的物理多次散射天空与自设环境，不引入外部 HDRI。贴图生成、图像渲染、灯具建模和导出脚本均保存在 `assets/blender/scripts/`。

`dual-bake-v8-preparation.json` 已记录 320,741 个三角形、100 个网格、37 个室内逻辑根节点、93 个室内稳定 ID 及 2 个外部环境 ID；最终导出及 `renders/asset-validation-v8.json` 已确认上述资产层级，GLB 为 45,313,752 字节、100 个绘制图元及 10 张内嵌图像，SHA-256 为 `fc7e1ba5bb7e9bda9594ac2fcd8dcc63469a9090e54686cbd444809e33cfc7b4`。早期 V2 源工程和 V4 / V5 / V6 导出记录保留作历史追溯。

## 历史 V8 网站试接入使用项

用户已授权本地试预览。V8 已完成烘焙、导出和资产校验，并由 `src/main.js` 接入；本节记录当前日夜资产来源，不代表最终视觉验收或部署授权。

- `public/models/orbital-atelier-v8.glb`：统一室内及外部节点层级，内嵌项目原创夜间烘焙图像。`public/textures/lighting-v8/` 提供日间图集和日景窗图；每态 8 组图集为 6×4096、1×3072、1×2048，由 Cycles COMBINED 40 采样生成。
- 日夜窗景均为本项目城市场景的独立 Blender 实际渲染；屏幕图形和新增灯具同为本项目制作。它们作为场景美术，不代表用户真实项目、经历或收藏含义。
- 网页采用无光照材质与日夜双纹理着色器混合，显示对应真实烘焙结果；地面接触阴影与环境图形由本项目程序生成，不使用旧 skybox、旧模板视频、壁纸或角色图像。
- 字体使用系统字体栈，图标为本次代码绘制的简单图形；旧模板字体文件不分发。
- 声音使用浏览器合成反馈与键盘音符，不加载旧背景音乐、钢琴采样或点击音频。
- 作者头像、项目图、分享图和社交链接退出使用；用户未提供内容仍标记“待补充”。
- V8 导出不使用 Draco，旧解码资源不分发。原版模板 MIT LICENSE 原样保留，Three.js 与 GSAP 的许可声明保存在 `docs/licenses/` 和 `public/licenses/`。

制作与光照准备通过 Blender MCP 核验；长时间完整烘焙由同一个本机 Blender 后台执行，脚本顺序见 [资产流程](ASSET_PIPELINE.md)。源场景、烘焙副本和最终可编辑日夜场景分别保存，保持来源及编辑过程可追溯。此次更新未改变上方第三方历史素材台账和依赖许可证据，也不构成发布放行。


## 字体候选历史 · V3（2026-09-22，02 已选定）

用户要求“多找几种字体让我验收 还有字体要有厚度”。新增 [本地字体对比页](http://127.0.0.1:5173/font-review-v3/index.html)，五份候选子集仅用于这一验收页；用户随后明确选择“寒蝉圆黑体立体厚字”，正式站现以单独扩展子集接入 UI V3（见后文）。上方 V2 实现和 QA 记录保留为历史。候选页面和厚度表现见 [FONT_REVIEW_V3.md](FONT_REVIEW_V3.md)。

| 候选 | 具体原始来源 | 本地网页文件 / 大小 | 随附许可与可追溯记录 |
| --- | --- | --- | --- |
| 标小智无界黑（400） | [官方仓库](https://github.com/maoken-fonts/unbounded-sans) / [具体许可](https://github.com/maoken-fonts/unbounded-sans/blob/v1.100/OFL.txt) | `public/fonts/review-v3/unbounded/review.woff2` / 38,588 字节 | SIL OFL 1.1；[原文](../public/fonts/review-v3/unbounded/LICENSE.txt) / [SOURCE.json](../assets/font-candidates/v3/unbounded/SOURCE.json) |
| 寒蝉圆黑体 Heavy（900） | [官方仓库](https://github.com/Warren2060/ChillRoundGothic) / [具体许可](https://github.com/Warren2060/ChillRoundGothic/blob/main/License.txt) | `public/fonts/review-v3/chill-rounded-heavy/display.woff2` / 82,120 字节 | SIL OFL 1.1；[原文](../public/fonts/review-v3/chill-rounded-heavy/OFL.txt) / [SOURCE.json](../assets/font-candidates/v3/chill-rounded-heavy/SOURCE.json) |
| 寒蝉无机体·宽体（500） | [官方仓库](https://github.com/Warren2060/ChillTanHei) / [具体许可](https://github.com/Warren2060/ChillTanHei/blob/main/License) | `public/fonts/review-v3/chill-tanhei/display.woff2` / 87,184 字节 | SIL OFL 1.1；[原文](../public/fonts/review-v3/chill-tanhei/OFL.txt) / [SOURCE.json](../assets/font-candidates/v3/chill-tanhei/SOURCE.json) |
| 得意黑（400） | [官方仓库](https://github.com/atelier-anchor/smiley-sans) / [具体许可](https://github.com/atelier-anchor/smiley-sans/blob/v2.0.1/LICENSE) | `public/fonts/review-v3/smiley/review.woff2` / 34,160 字节 | SIL OFL 1.1；[原文](../public/fonts/review-v3/smiley/LICENSE.txt) / [SOURCE.json](../assets/font-candidates/v3/smiley/SOURCE.json) |
| 站酷庆科黄油体（400） | [官方仓库](https://github.com/googlefonts/zcool-qingke-huangyou) / [具体许可](https://raw.githubusercontent.com/google/fonts/main/ofl/zcoolqingkehuangyou/OFL.txt) | `public/fonts/review-v3/zcool-qingke/review-qingke.woff2` / 18,508 字节 | SIL OFL 1.1；[原文](../public/fonts/review-v3/zcool-qingke/OFL.txt) / [SOURCE.json](../assets/font-candidates/v3/zcool-qingke/SOURCE.json) |

五份网页字体均由对应原字体子集化并转为 WOFF2，主名称已使用独立派生名称；保留原有轮廓、原生字重、版权与许可。OFL 允许在其条件下嵌入、修改、随软件分发；字体及派生文件继续按 OFL 分发，不单独售卖字体，不使用保留字体名作为派生主名称，不以作者名称作背书。它们不归入模板 MIT。详细原始文件版本、哈希与修改记录存于各 SOURCE.json；五份 WOFF2 合计 260,560 字节。

验收页房间底图沿用本项目已有的 `renders/night-warm-v13-after-web.png`，副本 `public/font-review-v3/room-night.png` 的 SHA-256 同为 `c38007f50ba4edb9ce534d39aec191247e95c1bb520512d1e0b89031cd6a9acc`，未引入第三方场景图。页面的浮雕厚度由 CSS 阴影表达，无新增外部图像材质。上述记录不代表字体已获用户视觉验收或网站已获部署授权。


## 正式展示字体首次接入记录 · UI V3（2026-09-22）

用户明确选择“寒蝉圆黑体立体厚字”，主站现使用 **寒蝉圆黑体 Heavy** 的本地派生 `Atelier Rounded Display`，原生 900 字重。字体方向已批准，接入后的最终视觉仍待反馈。本表保留首次接入的 510 字子集证据；后续长廊 540 字和立方体开场 548 字扩展见本页追加记录。[实现与检查范围](UI_TYPOGRAPHY_V3.md)记录正式 UI，本节与上方候选子集分开追溯。

| 项目 | 证据 |
| --- | --- |
| 原始来源 | [Warren2060 / ChillRoundGothic](https://github.com/Warren2060/ChillRoundGothic)，`ChillRoundGothic_Heavy.ttf` Version 3.700，原始 SHA-256 `8e008ecec9854ec2887cea9e28a7826c65c00409d532e0fe5bd01afe704e718e` |
| 正式网页文件 | `public/fonts/orbital-rounded/atelier-rounded-display-ui.woff2`，99,512 字节；510 字符 / 767 字形；原生字重 900 |
| 派生 SHA-256 | `9c1ecdc6cb0a42ed16519a1e31788757d1233933be1acee18924b532a6ab2d5b` |
| 许可与版权 | [随附 SIL OFL 1.1](../public/fonts/orbital-rounded/OFL.txt)；保留 ChillRoundGothic Project Authors 版权，字体内 Adobe / ChillType 版权记录保留，详情见 [SOURCE.json](../public/fonts/orbital-rounded/SOURCE.json) |
| 修改范围 | 字符子集化、WOFF2 转换、派生主名称重命名；510 字符轮廓验证一致，字重不变；比候选子集新增 `↗`，当前必需字符缺失 0 |
| 运行时 | 主站预加载本地 WOFF2；当前标题、导航、昼夜标签等采用该字形，立体侧面由 CSS 阴影绘制；正文保留系统字体 |

字体继续随版权和 OFL 分发，不单独出售，不以保留字体名作为派生主名称，不以原作者名称背书，不归入模板 MIT。当前源码变更不新增第三方模型、贴图或灯光环境，V13 资产和旧项目保持。本地实现不构成部署授权。


## 首页 B 主视觉（V14）

`public/textures/home/room-day-v14.png` 由本项目真实 V14 GLB 和已烘焙的日间贴图通过 Blender 渲染，透明背景，无外部素材或栅格修图。所有室内资产沿用本项目来源记录；对应渲染元数据为 `renders/homepage-b-room-render.json`。生成式首页概念 A/B/C 仅保存在 `docs/concepts/homepage-v2/` 供选型，不作为首页背景。首页继续使用已许可的寒蝉圆黑 Heavy 本地字体，未引入新第三方字体。


## 作品场景 B 实模 V1（2026-09-24）

用户附图选择 B“日光玻璃长廊”后，在独立 `assets/blender/works-gallery-v1.blend` 中完成新建筑、六个展位、中央陈列家具、小物件、程序材质与日夜灯光。展品为本项目原创几何占位，不代表用户真实作品。背景复用本项目原有 ENV_CITY 三维环境，未新增第三方模型、纹理或 HDRI。编号与英文占位标签使用 Blender 内置 Bfont，保留为源场景文字；后续网页导出计划转为几何。

`renders/works-gallery-v1/day.png` 与 `night.png` 是 Blender Cycles 实際渲染，非生成式概念图。概念 B 仅作获批设计参考，未进入网站。几何与图像校验、制作脚本和待验收状态见 [作品展厅 V1](WORKS_GALLERY_V1.md)。网站贴图烘焙、GLB 导出和转场尚未执行，当前源模型不代表网页性能结果。模板 MIT、已有依赖与字体许可保持原样。


## 作品长廊 V1 网站与纹理压缩（2026-09-24）

日夜八张 PNG 由本项目 Blender Cycles 原创场景实际烘焙；生成的八张 KTX2 与压缩 GLB 已接入本地网站。原 PNG/GLB 保留，几何和 86 个独立 ID 完全不变。KTX2 使用官方 Khronos KTX-Software v4.4.2 本地编码，工具来源、官方包 SHA-256 与完整原许可见 `tools/ktx-software/README.md`，工具不进入网页运行产物。

网页解码器来自已使用的 Three.js 0.172.0 所附 Basis Universal，位于 `public/basis/`，随附原 README、Basis 的 Apache 2.0 文本及 Three MIT 文本；具体文件校验见 `compression-report.json`。新运行资源不含第三方作品、模型、HDRI或人物内容，作品仍为待补充的原创几何占位。新代码仅本地运行，未推送或部署。

作品长廊新增文案沿用已批准寒蝉圆黑 Heavy，正式子集新增30字符；保留全部原510字符、900字重、派生名与原版权/OFL，540字轮廓及字宽核验无差异。当时的文件及SHA见 [字体补齐记录](FONT_GALLERY_V1.md)，上方99512 bytes / 510字符为历史版本；随后立方体欢迎文案扩展至548字符，见本页末尾记录。

## 房间动态屏幕与 V15 纹理（2026-09-24）

屏幕新增轮播图复用本项目真实 Blender 长廊日景、夜景渲染，与原有橙蓝雕塑画面一同展示；文件来源、SHA 和 KTX2 编码记录见 `public/textures/live-room/SOURCE.json`。这些图像属于场景展示占位，不作为用户真实项目。窗外动态使用原有城市渲染及本地程序着色器，没有引入第三方视频或远程图片服务。

V15 小物图集由原程序材质重新展开 UV 并通过 Cycles 烘焙。网页 KTX2 沿用上述官方 Khronos 工具与 Three/Basis 解码器；原 PNG 和源 GLB 保留。没有新增第三方模型、贴图、人物或 HDRI。模板 MIT、字体 OFL 与现有依赖许可继续保留。

## 作品长廊精简 V3

本轮只删除项目原创长廊背景资产，重新烘焙自身薄底座，并使用同一 Blender 工程真实渲染更新主屏轮播。未新增第三方图像、模型或字体；Sooah 模板许可证及既有素材来源保持。当前资产清单见 `WORKS_GALLERY_V3.md`，屏幕图来源见 `public/textures/live-room/SOURCE.json`。

## 长廊光影与天空 V1

四张地面/天空日夜贴图均由本项目 Blender 原创工程烘焙或渲染，未下载 HDRI、照片或第三方纹理。记录见 `GALLERY_ATMOSPHERE_V1.md` 和 `public/textures/gallery-atmosphere-v1/{SOURCE,SKY_SOURCE}.json`。

## 长廊框墙与玻璃 V4

连续框墙、实体建筑玻璃及新窗槽在本项目 Blender V4 源中重建。日夜图集、局部玻璃反射图、外围地面新投影及屏幕长廊画面均来自该原创场景；天空继续使用已记录的 V1 程序天空。没有新增第三方模型、HDRI、照片、字体或远程图像服务。材质实现见 `GALLERY_GLASS_V4_WEB.md`；反射、地面和屏幕图各自的 SOURCE.json 保留来源与校验记录。既有模板、字体与解码器许可证不变，作品展示仍为待补充占位。


## 立方体展开入场参考 · Abigail Bloom（2026-09-25）

用户明确指定 [Abigail Bloom 演示](https://abigail-bloom-portolio-bokoko33.vercel.app/)与[源码仓库](https://github.com/andrewwoan/abigail-bloom-portolio-bokoko33)，参考版本固定为 `3402ac0a989a38b7f9a221ee968836e223062e0d`。已检查该版本 `Experience/Preloader.js` 中 `firstIntro`、`secondIntro`，据其“欢迎方块 → 手势进入 → 房间与文字错峰出现”编排适配当前项目。

| 项目 | 来源与证据 |
| --- | --- |
| 固定源码 | [Preloader.js @ 3402ac0](https://github.com/andrewwoan/abigail-bloom-portolio-bokoko33/blob/3402ac0a989a38b7f9a221ee968836e223062e0d/Experience/Preloader.js)；本地副本 `assets/references/abigail-bloom/Preloader.js`，12,418 字节，SHA-256 `8a2953087d69825500ffc378f2b16b358a98831f402e420314853096e5a5b199` |
| 许可 | MIT；Copyright (c) 2023 Andrew Woan；[完整原文](../public/licenses/abigail-bloom/LICENSE.md)，1,068 字节，SHA-256 `2a488252f57fef867a3ffb666d28bbb1fb51805099828fa0d7d76430acff2984` |
| 来源记录 | [SOURCE.json](../public/licenses/abigail-bloom/SOURCE.json)，记录提交、函数、演示和适配范围 |
| 实际改写 | `src/cube-intro.js` 文件首部保留作者及来源注释；真实六面铰链立方体、现有房间包围盒、36件资产独立动作、状态与输入管理、原始变换恢复均按本项目模型适配 |
| 未引入的参考素材 | 未复制参考站房间模型、贴图、字体、作者姓名或作品内容；已有房间、配色、字体与“待补充”个人资料继续使用 |

MIT 的版权和许可文本随引用代码保留，单独存于 `public/licenses/abigail-bloom/`；原 Sooah 模板根目录 `LICENSE.md` 不删除或改写。此代码许可不扩展到参考站其他素材，也不改变字体 OFL、Three.js MIT 或 GSAP 原有许可。实现说明和自动检查范围见 [CUBE_INTRO_V1.md](CUBE_INTRO_V1.md)；浏览器验收由主任务继续，当前记录仅限本地接入。

## 正式字体当前修订 · 立方体欢迎文案 548 字（2026-09-25）

沿用用户已选择的寒蝉圆黑 Heavy、派生 family `Atelier Rounded Display` 和原生 900 字重。本次保留全部旧 540 字覆盖，为欢迎及身份文案新增 **“份到始扫来欢跳迎”8字**，没有引入新的字体来源。

| 项目 | 当前证据 |
| --- | --- |
| 网页文件 | `public/fonts/orbital-rounded/atelier-rounded-display-ui.woff2`，88,296 字节；548 字符 / 594 字形 |
| SHA-256 | `9f430c6b90775ab50ccb2539e99ab42509ce3d4b9fd51be4142496a3442535d0` |
| 修改与验证 | 从原 Heavy 文件重新子集化、转 WOFF2；548字输出轮廓与字宽逐一对比原字体无差异；保留原生900字重和此前重命名后的名字表 |
| 追溯 | [SOURCE.json](../public/fonts/orbital-rounded/SOURCE.json)保留此次新增字、原文件、旧510/540字修订和哈希；[CHARACTERS.txt](../public/fonts/orbital-rounded/CHARACTERS.txt)为当前覆盖 |
| 许可 | [SIL OFL 1.1 原文](../public/fonts/orbital-rounded/OFL.txt)与[NOTICE.txt](../public/fonts/orbital-rounded/NOTICE.txt)保留；Adobe、ChillType 和 ChillRoundGothic Project Authors 版权记录不改 |

字体继续按 OFL 单独分发，不归入模板或开场参考的 MIT。旧510与540字条目保留为历史证据。字体覆盖验证不等于浏览器排版或视觉验收通过。

## 原创轨道雕塑开场 · Orbital Intro V2（2026-09-25）

用户最新要求将一开始的方块替换成简洁、符合房间风格的模型，同时保留现有首次下滑和房间错峰展开流程。运行时已用本项目 Blender 原创 `welcome-orbit-v1` 替换旧六面立方体；上方 Cube Intro V1 条目保留为历史编排和许可记录，当前模型说明见 [ORBITAL_INTRO_V2.md](ORBITAL_INTRO_V2.md)。

| 项目 | 来源与证据 |
| --- | --- |
| 原创建模 | 深蓝薄椭圆底座、两瓣银色轨道环及少量铜端面、暖白陶瓷球；本项目参数化 Blender 几何与常量 PBR 材质，无第三方模型或图像 |
| 源工程 | `assets/blender/welcome-orbit-v1.blend`，221,337 字节；SHA-256 `0dbf0ed8d2978622d7df0aa8351843be0ec400832611a9c0d4d8a7a43b0f21dd` |
| 网页模型 | `public/models/welcome-orbit-v1.glb`，179,404 字节；4 个独立网格、8,024 个三角形、3 种材质、0 张贴图；SHA-256 `d86e2f3c71d676671c7a8a5dda5372444a584877957847dd48378d4ab523ecea` |
| 来源与结构记录 | [welcome-orbit-v1.source.json](../public/models/welcome-orbit-v1.source.json)，包含节点名、原始轴向、包围盒、制作来源与二进制导出统计 |
| 金属环境反射 | 由已使用的 Three.js `RoomEnvironment` 程序场景通过 `PMREMGenerator` 在准备阶段生成一次，沿用 Three.js MIT；未下载第三方 HDRI 或照片 |
| 延续许可 | Abigail `firstIntro` / `secondIntro` 编排的 MIT 和2023作者声明继续保留；原 Sooah 模板 MIT、现有 GSAP 声明、548字寒蝉Heavy派生字体 OFL 均不变 |

新轨道雕塑是开场临时模型，未修改房间或长廊资产，不是用户真实作品经历的替代内容。文件来源和导出统计不等于浏览器视觉、交互或性能验收；V2 当前源码的自动检查与浏览器报告由主任务最终补充，旧 Cube V1 的结果不自动沿用。此次仍只作本地预览。


## 房间 V17、长廊 V6 与终端 V3 材质（2026-09-30）

本轮仅重制房间、长廊和终端；关于我已获用户明确通过，不改其场景与材质。房间与长廊的布料、皮革、木材和水磨石复用已校验的 CC0 纹理，来源、原始文件 SHA 和许可证保留于 `assets/textures/about-atelier-v3/texture-manifest.json` 与同目录 `LICENSE-CC0-1.0.txt`。其余表面为本项目在 Blender 中制作的程序节点；没有把程序纹理称为扫描素材，没有新下载模型或 HDRI。两个场景的日夜反射 HDR 来自本项目实际场景渲染。

终端 V3 的 UV1 表面贴图来自其原创 Blender 材质烘焙；原始屏幕内容、UV0 和动画保留。文件定向 Blender MCP 承担材质调整、烘焙、渲染和模型导出，脚本辅助与 CPU 压缩如实记录，未将这套流程描述为纯手工制作。

`src/physical-surface.js` 的 CubeUV/GGX lookup 与局部 AgX、`src/terminal-tone.js` 的 AgX 使用已安装 Three.js 0.172.0 的 shader chunks。Three 原 MIT 文本保留于 `docs/licenses/three-0.172.0-LICENSE.txt` 与 `public/licenses/three-0.172.0-LICENSE.txt`。现有 Khronos KTX、Basis 解码器、Sooah 与 Abigail MIT、字体各自许可均保持。运行时光照压缩编码由本项目实现，来源与误差校验见 `docs/PHYSICAL_SURFACE_CONTRACT.md`。所有修改仅本地预览，未发布到仓库或域名。


## 房间 V20 黑白大理石（2026-10-01）

墙面使用 [ambientCG Marble005](https://ambientcg.com/a/Marble005)，顶部使用 [Marble002](https://ambientcg.com/a/Marble002) 的完整 4K PNG PBR 材质。两者均由 ambientCG 标注为程序制作，不能称作扫描材质。其 [CC0 1.0 许可](https://docs.ambientcg.com/license/)已核实；原包、官方元数据、许可网页副本和逐文件 SHA 位于 `assets/textures/room-marble-v20/`。正式素材以 Blender 材质节点重新标定、映射并烘焙进房间原有图集，没有修改深木地板或新增模型。

随网站分发的许可与来源为 [CC0 原文](../public/licenses/ambientcg-room-marble-v20/CC0-1.0.txt)及 [SOURCE.json](../public/licenses/ambientcg-room-marble-v20/SOURCE.json)。模板 MIT 和其他素材各自许可保持。


## 2026-10-01 — 长廊作品 01《糖壳暴食兽》

用户提供的 1080p MP4 原样复制到 `public/media/works/sugar-shell-glutton/demo-1080p.mp4`（SHA256 `f2c959c4283c46b64d920433e1425ffb0ea525cc3e13b1d7f6f251a4d66e32e6`）。五张 WebP 是该视频的直接实机帧提取，并非新生成图片。内容、截帧时间与贡献声明见 `docs/sugar-shell-glutton-content-evidence.json`。长廊封面是本地 Canvas 排版，保留已有模型网格与 UV；网站字体和原模板许可证维持。视频制作说明提及 AI、Blender 脚本和 CC0 特效素材；本次仅接入用户提供的成片，不将该说明当作逐项第三方许可核查。仅本地预览，未发布。


## 2026-10-02 — 长廊展位 02–05 的既有项目素材

接入用户指定的夜班便利店、相机、Blender 客厅与跑车、龙卷风特效和六个 AI 软件项目。具体原始路径、转换方式及哈希见 `gallery-exhibits-23-sources.json`、`gallery-exhibits-45-sources.json`。电商三张新图通过 CUA 从本机正在运行的最新工作区只读截取；经营数据为合成演示数据。没有新购买或下载外部素材，没有把参考概念图称作实际渲染；仅本地展示，未发布。

这些是用户要求展示的既有作品，不因此推定作品内所有第三方模型、商标、字体、音频已获得新的授权；沿用各原项目许可记录，来源清单不等于逐项权利审查。网站原 Sooah/Abigail 模板及当前字体、Three.js 等许可证保留。封面为本地 Canvas 排版，不修改原 GLB。


## 2026-10-02 - UI typography and abstract homepage light

Microsoft YaHei is a local system-font preference only; no Microsoft font is redistributed. This Mac falls back to PingFang SC. The existing licensed DouyinSans Bold-derived Atelier Forge Display title subset now covers 1085 characters; its original outlines, widths, OFL and source records remain in public/fonts/orbital-forge/ and assets/font-candidates/v4/production-validation.json. New background and loading light effects are project-authored code, with no new image/model asset. The abandoned architectural candidate was not installed. Impeccable is locally installed design guidance under Apache-2.0; pinned provenance, LICENSE and NOTICE are in /Users/a90/.codex/skills/impeccable/. Existing Codrops and template attribution is preserved.
