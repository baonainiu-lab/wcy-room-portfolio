# 模板交互与 Blender 资产交付约定

当前本地站点使用 **V15 房间资产**，包含小物高精度 UV 重分配、窗右上净空修复、连续白壳工作椅恢复，以及真实重渲的屏幕和城市窗景。运行版使用 KTX2 压缩 GLB；文件、层级和纹理校验已通过，最终浏览器与性能验收单独记录，不将文件校验视为稳定 120 FPS 的证明。详见 [房间 V15 记录](ROOM_PRECISION_V15.md)。

## 当前 V15 文件与交付

| 内容 | 路径 |
| --- | --- |
| 可编辑 PBR 源 | `assets/blender/orbital-atelier-v15.blend` |
| 网页烘焙准备工程 | `assets/blender/orbital-dual-bake-v15.blend` |
| 当前网页运行模型 | `public/models/orbital-atelier-v15-compressed.glb` |
| 原始 PNG 导出模型 | `public/models/orbital-atelier-v15.glb` |
| PNG 源图与 KTX2 运行贴图 | `public/textures/lighting-v15/` |
| 导出与全量文件验证 | `assets/blender/dual-lighting-v15-export-report.json`、`assets/blender/texture-precision-v15-validation.json` |
| 压缩来源、参数与逐图哈希 | `assets/blender/texture-precision-v15-compression.json` |
| 工作椅恢复与独立验证 | `assets/blender/work-chair-v15-refinement.json`、`assets/blender/work-chair-v15-validation.json` |
| 椅子精修前的 V15 中间源 | `assets/blender/v15-pre-chair/` |

最终房间为 **413,855 个三角形、102 个绘制 primitive、197 个节点、19 种材质**。37 个室内根资产、93 个室内 ID 和 2 个环境 ID（共 95 个）保留，层级、转轴与交互绑定保持。工作椅恢复原高精度几何；不能将本轮概括为“所有几何不变”。

每个日夜状态有 **12 组 atlas**：8×4096²、3×3072²、1×2048²。24 张图集加 2 张 3072×1344 窗景与 1 张 2880×1200 原作屏幕，共 **27 张 PNG**；均保留原图并提供 KTX2。新增烘焙使用 Cycles 96 samples，窗景与屏幕由原 Blender 场景真实重渲，未插值放大。A2/A9/A10 重新分配小物 UV；工作椅单独使用 A11，白壳两面采用连续参数 UV。具体复用图集、烘焙来源和修窗前后快照见 V15 记录及逐图 manifest。

运行 GLB 为 **70,844,508 字节**，SHA-256 为 `3787d233559af32f2e3ababb21b71c56c5805e7c7f2e286f87634efe8cd6bffd`；原始 GLB 为 70,281,488 字节，SHA-256 为 `5e919bbc24ccbf0b097a9c4c1b181d48b538d6ff25c0899d1f5cb8d949e15c15`。KTX2 使用 UASTC quality 2、Zstd 9 和完整 mip 链，压缩报告确认非图像数据、几何与层级保持；该压缩用于降低 GPU 纹理占用，不以传输文件必然更小或稳定帧率作为结论。

V15 流水线由 `prepare_texture_precision_v15.py`、`repair_window_clearance_v15.py`、`run_texture_precision_v15.py` 完成主要 UV/窗边与两态烘焙；独立窗景/屏幕使用 `render_window_states_v15.py`、`render_screen_art_v15.py`，由 `bind_precision_images_v15.py` 持久绑定。最后的工作椅补修与最终原 GLB 导出使用 `refine_work_chair_v15.py`，压缩使用 `scripts/compress-room-v15.py`。V14 与更早源保持，独立资产未为减少绘制而合并成不可交互房间。

## 当前界面、首页与作品场景

展示字体采用用户指定的 **寒蝉圆黑体立体厚字**：本地 Heavy / 900 字形，立体厚度由 CSS 阴影表现。当前来源、许可与字集见 [字体 V3](UI_TYPOGRAPHY_V3.md)、[长廊字体补齐](FONT_GALLERY_V1.md)及[素材台账](THIRD_PARTY_ASSETS.md)；下文 Noto Serif SC 为旧 V2 历史。

首页采用已选定的 **B“日光画册”**，明亮米白与大标题版式已接入；主视觉使用真实房间预览，支持缓慢旋转与拖动，见 [首页 B](HOMEPAGE_B_V2.md)、[实时房间首页](HOMEPAGE_ROOM_V7.md)和[首页动效](HOMEPAGE_MOTION_V7.md)。作品选项及主屏点击已连接 **B“日光玻璃长廊”** 第二场景，包含平滑镜头过渡、独立作品物件与返回房间。当前为[连续框墙与实体玻璃 V4](WORKS_GALLERY_V4.md)：两端框墙及背梁形成闭合连接结构，建筑玻璃厚 30–32mm，和展柜玻璃分开材质；V3 精简场景记录保留为[历史](WORKS_GALLERY_V3.md)，城市与外围建筑没有恢复。个人作品资料未提供的部分继续标为待补充。

V4 可编辑源为 `assets/blender/works-gallery-v4.blend`，准备源为 `assets/blender/works-gallery-bake-v4.blend`，当前运行模型为 `public/models/works-gallery-v4-compressed.glb`，SHA-256 `da7f6045703dee51f4ea83f644451293992ba5e2fc7b86a42e41a98779577bbf`。77 IDs、142 nodes、80 meshes/primitives、542976 三角和 6 材质；四组 4096/4096/4096/1024 图集日夜均以 64 samples 真实重烘。建筑玻璃使用[静态局部反射 probe 与 Fresnel](GALLERY_GLASS_V4_WEB.md)，探针实际 Web 坐标 `[0.12,2.7,-3.36]`；元数据见 `public/textures/works-gallery-v4/reflection-SOURCE.json`。新墙体投影重烘为 `public/textures/gallery-atmosphere-v2/`，天空继续复用[符合太阳方位的物理天空 V1](GALLERY_ATMOSPHERE_V1.md)。[连续三维切镜](SCENE_TRANSITION_V3.md)保留。V4 资源、几何、法线及源→准备→GLB 坐标验证通过；当前状态为 **`local_integrated_browser_verification_pending`**，已接入本地网页，浏览器及性能验收待写入 `renders/works-gallery-v4/web-verification.json`，不据文件检查宣称已通过网页验收或稳定 120 FPS。

保留模板的房间浏览、镜头控制、加载进入与物件反馈方式。自由小物放大时同时保持底部净空；装配部件限制倍率，避免穿入机构。角色仍暂不接入。屏幕轮播、窗外云雾/交通光点和近景镜头保护的实现与验证范围见 [V15 记录](ROOM_PRECISION_V15.md)。当前仅在独立项目本地预览，不推送旧仓库，不部署旧域名。

## 历史 V13 文件与流程

以下 V13 及更早的模块数、资产数量、字体、交互与性能数据均为对应阶段历史，不能代替当前 V15 的浏览器或性能验收。V13 夜间八图集重烘、源 / GLB 导出及连续性校验曾完成；当时接入 UI 字体 V2，并通过相应构建与浏览器检查。

| 内容 | 路径 |
| --- | --- |
| 完整源 / 准备工程 | `assets/blender/orbital-atelier-v13.blend`、`assets/blender/orbital-dual-bake-v13.blend` |
| 网页模型 / 贴图 | `public/models/orbital-atelier-v13.glb`、`public/textures/lighting-v13/` |
| 灯光设计 / 烘焙状态 | `assets/blender/night-warm-v13-design.json`、`assets/blender/night-warm-v13-status.json`（`complete`） |
| 交付 / 日景源核验 | `assets/blender/night-warm-v13-delivery.json`、`assets/blender/source-day-v13-verification.json` |
| 资产 / 连续性验证 | `renders/asset-validation-v13.json`、`renders/night-warm-v13-continuity-check.json` |

GLB 为 46,178,184 字节、373,203 三角形、100 个绘制图元和 10 张内嵌图像；37 个室内根资产、93 个室内 ID 与 2 个环境 ID 保留。GLB SHA-256 为 `44178b2372dfb4978da24fb6910c0d279bc353a9ed4936656fb52d45e18824f9`；完整源为 73,860,523 字节，SHA-256 为 `2469222a77fc326d34223785a15675cf1abf65ecdf6c9297ca2619d9d9f16d17`。

`night_warm_v13.py` 在 V12 源的夜景配置桌下与窗下三处局部暖光，并调整既有灯具，另存 V13 完整源与准备工程。`run_night_warm_v13.py` 复制原贴图、重烘夜间图集 0–7、导出 GLB，再校验 9 张日间图像哈希；流程已完成。几何 / UV / 法线 / 索引及层级变换与 V12 精确一致，可编辑白天场景签名也一致。暖光进入现有图集，不新增网页实时灯、可见几何、绘制图元或图集分配。详见[夜间暖光记录](NIGHT_WARM_V13.md)。

V13 阶段的 UI 字体为本地 Noto Serif SC 派生子集，按 OFL 1.1 保留来源与许可，详见[字体 V2](UI_TYPOGRAPHY_V2.md)及[素材台账](THIRD_PARTY_ASSETS.md)。UI V1 已通过的检查保留为历史。本轮[V13 + UI V2 性能采样](../renders/performance-night-warm-v13.json)为 844×795、DPR 2 的夜间静置画面，51.12 秒 / 8 次快照，FPS 中位数 120.48、帧间隔 P95 为 9.8–10.2 ms，`errors: []`，未证明稳定 120 FPS；完整范围见[预览检查](PREVIEW_CHECK.md)。

## 历史 V12 精度制作流程

`refine_architecture_quality_v12.py` 从 V11 源修复 8 个建筑对象的曲线、平滑 / 硬边、法线和 6 段倒角，保存并重新打开核验。准备时 `precision_budgets` 指定建筑 `room_static` 不 Collapse、两终端各 10,000、盆景 baked owner 18,000。其它资产预算与独立 ID 保留。

`run_precision_v12.py` 使用 `include_shading=True` 比较位置、面角拓扑、BakeUV、世界矩阵、角法线和平滑面标志，确定图集 0、2 需要重烘，两态均已完成；1、3–7 通过精确一致验证后复用，保留此前的间接光近似。随后导出并执行 `verify_v8_export.py 12` 校验，当前通过。

UV helper 是未启用的实验：实际 V12 建筑纹素密度约 +14%，但可见平台约 −29%，未形成可接受的净收益。本轮保持 4K 现有布局策略，不因完成几何修复就声明纹理、玻璃材质或全部像素化问题均已解决。依据及测量限制见 [V12 精度记录](MODEL_PRECISION_V12.md)。

## 历史 V10 → V11 制作流程

1. `thicken_walls_v10.py` 从 V9 完整源工程制作 V10：墙体向外增厚 0.16 m、上沿增高 0.35 m，配套修改金属框并增加 L 形墙脚承托。源对象 ID、室内窗与家具变换保留。
2. 调用 `prepare_dual_bake_v8.prepare()` 时指定 V10 源、输出及报告路径和 `revision=10`，生成 V10 准备场景；`run_wall_lighting_v10.py` 重新烘焙日夜全部 8 组图集并导出 V10。该阶段已完成。
3. `fix_window_junction_v11.py` 的 `build_and_save()` 从 V10 源创建 V11，在墙顶金属带和展示柜后沿局部避让窗角，并输出几何检测报告。窗框与窗景位置不变；详细净空及检测范围见 [墙体记录](WALL_STRUCTURE_V10.md)。
4. 对 V11 完整源调用同一准备函数，设置 `output_path` 为 `orbital-dual-bake-v11.blend`、`report_path` 为 `dual-bake-v11-preparation.json`、`source_label` 为 V11 源文件、`revision=11`。
5. 运行 `run_window_junction_v11.py`。它先对 V10 / V11 中图集 1–7 的几何及 UV 生成指纹并精确比较，验证通过才沿用对应图像；然后分别重烘建筑图集 0 的日夜两态，最后导出 V11。结果与进度写入上述报告。
6. `python3 assets/blender/scripts/verify_v8_export.py 11` 验证模型层级、资产 ID、内嵌图像和两态外部图像，该历史版本通过。当前版本的浏览器检查见预览记录，不将文件校验等同于用户视觉验收。

本机长烘焙继续使用实际 Blender 后台进程；几何、光照和准备场景由 Blender 工具制作。源工程、烘焙副本和网页导出分别保留，不为性能优化合并独立交互资产。

## 历史 V8–V13 光照与网页显示

每个状态 8 组图集：6×4096、1×3072、1×2048，Cycles COMBINED 40 采样；AgX 写入 sRGB 图像，网页采用无光照材质，不重复色调映射。V13 将全部 8 张夜间图集重烘；8 张白天图集与日景窗图沿用 V12，哈希逐字节一致。夜间图集随 GLB 内嵌，日间图集和窗景单独载入，约 1.5 秒混合切换。

日景继续使用真实 Sun 与物理多次散射天空。窗洞阴影射线透射、摄影机不可见的屋顶挡光与窗框投影代理属于本项目的烘焙制作手段，不导出为网页可见几何。屏幕、城市日夜窗景均来自本项目 Blender 实际渲染。

夜间背景已在 `src/exterior-atmosphere.js` 压暗；`src/dual-lighting.js` 在夜间对外部泊位图集 5 乘以 0.28、展廊图集 6 乘以 0.12，在线性空间执行。室内及白天不作这项曝光调整；V13 夜景目视检查已完成，暖光局部可见且墙面仍冷暗，昼夜切换、显示屏打开作品、Esc 关闭回归已通过。

## 历史 V12–V13 交互与验收记录

- 保留模板 OrbitControls、加载进入、物件反馈和“作品 / 关于 / 联系”面板机制；物件由稳定 ID 映射，不依赖旧房间名称。
- 常规小资产悬停默认 1.8 倍；实体入口及家具 / 落地灯等大件采用较小倍率，单个资产可用 `hover_scale` 显式覆盖。点击播放自身动作，键盘音符由浏览器合成。
- 角色保持暂不接入；资料与物件个人含义缺失处标记“待补充”。
- 用户先前要求重做旧界面，现已明确批准按[新 UI 概念](concepts/ui-v1/README.md)实现。顶部导航、底部控制胶囊、单物件提示和面板样式已接入，指定浏览器 QA 已完成；[实现记录](UI_CONCEPT_V1_IMPLEMENTATION.md)与[浏览器证据](../renders/ui-v1-browser-check.json)记录实际范围，用户最终视觉验收仍待完成。V12 模型及日夜贴图不因此修改。
- 新 UI 接入前，V12 已检查日夜画面、白天低角度旋转及拉远 3 档、镜头复位、独立花瓣 1.8 倍悬停 / 点击动作、作品面板开关；遥测 `errors: []`。仅声明实际操作范围，证据与截图见[预览检查](PREVIEW_CHECK.md)。
- 新 UI 接入前的 V12 白天静置采样 42.07 秒 / 9 次快照，844×795、DPR 2，无并行 Blender 渲染，FPS 中位数 120.48、帧间隔 P95 为 8.9–9.2 ms；[性能报告](../renders/performance-lighting-v12.json)保持 `stable120Verified: false`。V9 及更早数据只作历史基线。仅在独立项目本地预览，不上传或部署。
