# 彩色终端开场 V3

> 历史版本：2026-09-25 的展开穿模修复见 [入场穿模修复 V4](ENTRY_COLLISION_V4.md)。以下测试与时序记录对应修复前版本。

2026-09-25。本轮按用户最新要求，欢迎页使用独立、有色、符合房间风格的小模型，不把完整房间缩小放在首页，也不将材质改成统一灰色。保留先展示模型、首次进入后展开并接入房间的两段节奏。仅用于本项目本地预览；未部署、未修改旧项目，页面文案沿用现有内容。

当前运行资产为 `welcome-terminal-v1.glb`。终端通过 Blender MCP 调用 Blender 标准建模操作、材质与关键帧制作，保存可编辑 `.blend`，并导出原生 `TerminalUnfold` 动画。网页加载真实 GLB，由 `AnimationMixer` 采样该动画；没有在网页代码中生成终端几何。`src/cube-intro.js` / `createCubeIntro` 是沿用的接口名称，当前已不创建六面方块。

控制器 **15/15**、输入及房间分组 **16/16**、真实资产 **8/8**、开场光照模块 **4/4** 检查通过。最新追加要求为开场不要出现尚未就位家具的多余阴影，已接入图集 **0 / 1 / 8** 的真实开场烘焙。主任务已反馈桌面欢迎、首次滚轮、重复滚轮、进入后保温杯点击，以及最终冻结 2.8 秒时桌面和地毯的大块阴影轮廓消失；播放中改为 390 × 844 后也已完成并恢复控制。本地浏览器检查已完成，共 13 项实际观察记录，证据及最终源码哈希见 [浏览器记录](../renders/terminal-intro-v3/web-verification.json)。包含首次进入、重复输入、手机尺寸轻扫、播放中改尺寸、跳过、减少动态效果、错误重试及入场后的交互。手机检查使用桌面浏览器视口和指针手势；本轮未验证稳定 120 FPS，最终视觉仍待用户反馈。

## 实际资产与来源

| 项目 | 当前内容 |
| --- | --- |
| Blender 源 | `assets/blender/welcome-terminal-v1.blend`，4,263,821 字节 |
| 建模操作记录 | `assets/blender/build-welcome-terminal-v1.py`；在独立 `WELCOME_TERMINAL_V1` 场景内使用原生操作和关键帧 |
| 网页模型 | `public/models/welcome-terminal-v1.glb`，4,306,676 字节 |
| 层级 | 18 个独立 mesh，11,294 个三角形；`seed.base`、`seed.lid`、`seed.dial`、`seed.rail` 四个根 |
| 材质 | 深蓝 `#244f70`、银钛 `#b4c4cf`、深色橡胶 `#101b26`、暖色细节 `#efad59`、橙色 `#f58036` 五种 PBR，加独立屏幕位图材质 |
| 默认尺寸 | glTF 米制、Y 向上；约 2.81 × 0.71348 × 1.81 m，打开后高约 1.64105 m |
| 原生动画 | `TerminalUnfold`，实际时长 1.6166666746 秒；盖板平移和三组四元数旋转，共 4 轨、每轨 97 个关键帧 |
| 完整来源和检查 | [资产来源](../public/models/welcome-terminal-v1.source.json)、[真实 GLB 检查](validation/welcome-terminal-v1.json) |

SHA-256：

- Blender：`10263463500d711ca38b2c5cf03805131a2526365a211921736d82dbf64dfdc1`
- GLB：`00052405d86acf54031f1b874ecf370c8afa1e75e5f92ccd0f3dda5414642d24`
- 屏幕 PNG：`e507d4952d56eedce460abd2775b3ee5f9be281db358afdb074425aba488f59d`

屏幕使用已在本项目制作并授权使用的原创图像 `public/textures/lighting-v15/screen-art-render.png`。它是原房间 Blender `SCREEN_ART` 场景的实际 Cycles 渲染，2880 × 1200，来源与原始渲染参数见 [V15 屏幕记录](../public/textures/lighting-v15/screen-v15-manifest.json)。终端内嵌 PNG 与该文件字节哈希完全相同，没有新增第三方模型或图像。该原创屏幕的来源与下述 MIT 编排代码许可分别记录，不把 MIT 误作新图像的来源。

导出坐标下，盖板绕局部 X 从 +12° 打开到 +95°，同时原点由 `[0, .285, .45]` 移至 `[0, .285, -.65]`；旋钮绕局部 Y 转至约 −45.8366°，滑轨绕局部 Z 转至约 +18.3347°。Three.js 加载器把点号名称转成 `seedbase` / `seedlid` / `seeddial` / `seedrail`，原始名称保存在 `userData.name`。实际控制器使用绑定解析定位动画节点，不按未转换名称盲查。

## 源码中的实际节奏

`main.js` 先加载并预编译原房间的正常双态光照程序，再加载开场干净图集、终端及其动画，建立开场控制器并预热临时程序，随后才调用 `ready()`。因此结束时恢复正常光照会复用预热过的程序。欢迎阶段完整房间不可见；显示彩色终端、米白背景与现有欢迎文案。终端约 0.7 秒出现，0.5 秒起调整位置，0.85 秒起欢迎文字逐字升起，1.75 秒起进入按钮淡入。桌面模型偏左；不大于 700 px 的视口使用上方居中构图。

下面的零点是首次进入手势触发，时间来自当前 `src/cube-intro.js` 和 `src/room-entry.js`：

| 相对时间 | 当前行为 |
| --- | --- |
| 0 秒起 | 欢迎文字及进入按钮退场，进入条件同步关闭，重复手势保持锁定 |
| 0.1–1.9 秒 | 相机、目标和终端位置平滑接近房间构图；终端的放大目标宽度按房间宽度的 62% 计算 |
| 0.5–2.1 秒 | 用暂停的 `AnimationAction` 绝对采样完整 `TerminalUnfold`，保留 Blender 中的盖板铰链与平移 |
| 1.35–3.0 秒 | 原 V15 房间开始可见，围绕实际地面支点从原比例的 0.025 等比展开至 1 |
| 1.7–2.35 秒 | 临时终端保持原不透明材质，等比缩回地面支点后隐藏；不再叠加半透明屏幕或改材质透明度 |
| 1.75 / 2.05 / 2.45 / 2.55 / 3.10 秒起 | 墙面陈设、主要家具、桌面物件、设备、工作椅依次交叠进入；每件再叠加独立组内偏移 |
| 2.15 秒起 | 现有姓名和身份文字逐字进入，继续保留待补充内容 |
| 2.2–3.65 秒 | 原有地面背景、天空及外部模型逐步恢复；建筑、桌面、茶几和地毯仍使用干净图集，接触阴影仍关闭 |
| 最后物件完成后 0.02 秒起 | 在 0.45 秒内从干净图集过渡回正常光照，同时恢复接触阴影；当前约为 4.24–4.69 秒 |
| 约 4.71799 秒 | 最后动作和身份退场完成，精确恢复房间姿态、移除输入锁并恢复交互 |

终端与房间整体均等比缩放；房间内部 36 个逻辑根沿用各自的铺展、落定、滑入、倾转等动作，不合并其独立子组件。五组数量为 7 / 6 / 9 / 13 / 1。每件时长根据真实包围盒及独立节奏值计算，范围为 0.5–1.25 秒；椅子额外旋转 0.45 圈并回到原始姿态，没有另加旧版的收尾时长。总体结束时间由实际动作末端计算。

终端与原房间材质的颜色、原图和原几何保留。开场期间只为图集 0 / 1 / 8 临时叠加采样钩子，将真实干净彩图与原双态光照结果按同一 UV 混合，不做 RGB 提亮、截断或灰色替换；完成后恢复原编译钩子及缓存键。终端灯光与 PMREM 环境属于临时资源。完成、跳过和释放均恢复原房间 position / quaternion / scale；主入口在完成时 `dispose()` 开场光照，释放三张干净贴图，临时终端资源也按原归属释放。

## 开场干净光照的实际烘焙

新贴图仅位于 `public/textures/intro-clean-v1/`，来源见 [SOURCE.json](../public/textures/intro-clean-v1/SOURCE.json)，验证见 [validation.json](../public/textures/intro-clean-v1/validation.json)。Blender 使用原 `orbital-dual-bake-v15.blend` 的 `WEB_DUAL_V8` 场景、原 PBR 基色与微表面纹理，保留四个建筑/平台接收网格的原几何和 `BakeUV`；其余 220 个对象暂时隐藏，关闭接收网格对阴影射线的可见性，在三盏宽面积灯和环境光下重新计算 Cycles COMBINED 彩图。开场烘焙的发光强度降至原值 20%，具体灯光和材质参数保留在来源记录中；没有重绘像素或在前端抬高 RGB。

随后实际 GPU 画面在 2.8 秒仍显示桌面和地毯中原先烘焙的物件轮廓，因此追加图集 1 的独立接收面烘焙。该轮保留桌、茶几、地毯三个原始网格和 UV，暂时隐藏 221 个其他对象，沿用第一轮的灯光与烘焙参数；图集 0 / 8 的 PNG 和 KTX2 完全不变。追加来源、独立预览与保护哈希见 [atlas-1-SOURCE.json](../public/textures/intro-clean-v1/atlas-1-SOURCE.json)。

| 图集 | PNG / 网页 KTX2 | 完整 mip 层数 |
| --- | --- | --- |
| 0 | `day-0.png` / `day-0.ktx2`，4096 × 4096 | 13 |
| 1 | `day-1.png` / `day-1.ktx2`，4096 × 4096 | 13 |
| 8 | `day-8.png` / `day-8.ktx2`，3072 × 3072 | 12 |

三图保持原图集分辨率，KTX2 为 sRGB，方向 `rd`，通过官方 `ktx validate` 和 PNG 解码检查；尺寸、内容哈希、压缩与真实接收面预览均有记录。烘焙没有保存覆盖原 Blender 文件。追加图集 1 时，**73 个受保护文件哈希全部保持不变**：原有 69 个源工程、模型、日夜贴图及根许可证，再加已验证的图集 0 / 8 四个 PNG / KTX2 文件。新增图集只用于欢迎后的组装阶段，不替换正常房间的日夜图集。

`src/intro-lighting.js` 在原 dual-lighting 钩子之后采样，沿用 `vMapUv`，保留共享的日夜混合 uniform。所有物件完成前，干净图集权重保持 1、正常阴影权重保持 0；随后统一过渡到原图。模块只拥有三张新贴图，加载或材质绑定失败会释放资源并回滚已安装钩子，正常恢复与重复释放也有检查。

## 输入、恢复与检查边界

首次向下滚轮、单指上滑超过 16 px、进入按钮或进入键触发一次。播放期间保持输入锁，避免惯性滚动传给 OrbitControls；向上滚轮、多指触摸和缩放滚轮不触发进入。窄屏鼠标或笔的上滑另有 24 px 阈值与竖向意图判定，不等同于真实手机触摸验证。跳过、Escape、减少动态效果及中途切换减少动态效果均恢复完整房间。

| 检查 | 结果与范围 |
| --- | --- |
| [终端控制器](validation/terminal-intro-v1.json) | 15/15；真实 GLTFLoader、AnimationMixer、GSAP 与生产控制器，覆盖一次性进入、native clip、不透明收回、最后物件完成后恢复阴影、精确恢复、跳过、resize、减少动态效果、释放与 DEV 检查入口。DOM、图像解码和 GPU PMREM 为受控替代，不是浏览器画质或帧率测试 |
| [输入与分组](validation/cube-intro.json) | 16/16；最终源码重跑，记录的控制器、输入、room-entry 和 V15 模型哈希全部与当前一致；覆盖真实输入事件逻辑、V15 几何层级与分组动作 |
| [终端资产](validation/welcome-terminal-v1.json) | 8/8；嵌入纹理、法线、UV、材质、动画及尺寸。无零面积三角；指示灯倒角有 126 个极小但非零三角，报告保留该局限 |
| [开场光照模块](validation/intro-clean-lighting.json) | 4/4；真实 Three 材质与着色器钩子的 CPU 检查，覆盖 UV 彩图混合、原钩子恢复和资源归属，以及加载失败、绑定失败的回滚清理 |
| [干净贴图资产](../public/textures/intro-clean-v1/validation.json) | PNG 解码、KTX2 验证、完整 mip、源文件保护均通过；真实烘焙与接收面预览证据独立保留 |
| 浏览器 | 主任务已报告桌面欢迎、首次滚轮、重复滚轮、进入后保温杯点击通过；最终冻结 2.8 秒时 `clean.maps: 3`、`progress: 0`、`shadowReveal: 0`、`errors: []`，桌面和地毯的大块烘焙轮廓消失。播放中从自然视口改为 390 × 844，确认 `phase: playing`，随后 `complete`、`controlsEnabled: true`、`clean.disposed: true`、`maps: 0`、`slots: [0,1,8]`、`errors: []`；这是桌面视口调整，未称为手机实机验证。整体最终结论待 `renders/terminal-intro-v3/web-verification.json` |
| 性能 | 本轮没有新的 120 FPS 实测，Node 检查不证明呈现性能；旧房间性能记录不能替代本开场的测量 |

`DEV + qa + introAt` 三条件同时满足时，才允许暂停同一生产时间线检查指定时刻；不创建替代场景。普通访问和生产构建不走该检查入口。本轮浏览器结果由主任务另行保存，此文档未新增或伪造截图、通过项或最终验收结论。

原 V15 房间与长廊模型继续使用现有资产；保护基线见 `renders/works-gallery-v4/protected-baseline.json`。旧 V15、旧长廊 V3 和根许可证的哈希保留，当前长廊 V4 也未因开场替换而改动。

## 历史与许可

[方块 V1](CUBE_INTRO_V1.md)和[轨道雕塑 V2](ORBITAL_INTRO_V2.md)保留为历史，旧浏览器截图与通过记录不代表本版。把真实房间折叠后放在首页的 `room-unfold-v1` 已被用户否决，当前为 **experimental/non-active**，不在运行模型路径中；[严格几何报告](validation/room-unfold-v1.json)仍为 **fail**：19,542 个三角的法线未能保持。它不因位置、UV 或压缩检查通过而成为已验收资产。

两段编排参考 Andrew Woan 的 Abigail Bloom 项目固定提交 `3402ac0a989a38b7f9a221ee968836e223062e0d`，对应 `Experience/Preloader.js` 中 `firstIntro` / `secondIntro`。[MIT 原文](../public/licenses/abigail-bloom/LICENSE.md)、Copyright (c) 2023 Andrew Woan 和[来源记录](../public/licenses/abigail-bloom/SOURCE.json)保留；副本位于 `assets/references/abigail-bloom/`。本轮适配为独立 Blender 彩色终端、原生滑动铰链动画、现有 36 件房间物件及输入恢复，不使用上游模型、贴图或个人内容。Sooah 根许可证及既有字体许可不改动，来源范围沿用[第三方素材台账](THIRD_PARTY_ASSETS.md)。
