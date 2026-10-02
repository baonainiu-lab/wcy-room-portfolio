# C「标志升起」主首页接入

状态（2026-10-01）：**保留用户选择的 C「标志升起」编排；用户随后否决 crossfold-v3，并明确选择 Logo C「轨道星核」。V4 已制作接入，CPU 门控检查 9/9 通过；新 Logo 与完整 Room19 的桌面/手机浏览器联检通过，见两份最新浏览器记录。** 选型确认不等同于接入后的最终视觉验收，也不包含部署。

## 选型与历史评审

用户选择评审页的 C「标志升起」：标志轮廓随进度描绘，准备完成后标志缩小上移，遮罩抬起，露出首页终端展示。主首页适配范围为加载界面、对应动画及新 SVG 标志；既有真实 startup gate 保持不变。

历史评审入口为 `/loader-review-v1/index.html`，C 直达入口为 `/loader-review-v1/index.html#C`。A/B/C/D 四个方案继续保留供回看。评审页仍是模拟进度与历史首页截图，不代表主首页加载状态或最新渲染效果；说明见 [评审 README](../public/loader-review-v1/README.md)。

## 上游来源与许可

动画来源为 [Codrops / PagePreloadingEffect](https://github.com/codrops/PagePreloadingEffect/tree/7a7893f4145f1dcfcf5dccd1ec893b24170fc987)，固定提交 `7a7893f4145f1dcfcf5dccd1ec893b24170fc987`。已核验的相关文件为 `js/pathLoader.js`、`js/main.js`、`css/effect1.css`、`index.html` 与 `README.md`。

适配依据为 `PathLoader` 的路径长度描边算法，以及 `effect1.css` 中加载元素退场、标志缩小上移、整片 header 上移及内容进入的分层编排。制作记录应区分 Codrops 动画适配、本站控制逻辑及本站 SVG 标志，不把改写后的动画标为完全原创，也不将 SVG 标志记为 AI 概念图或 Blender 制作。

许可与固定来源材料保存在 `public/loader-review-v1/source/`：

| 本地记录 | 内容 |
| --- | --- |
| [ATTRIBUTION.md](../public/loader-review-v1/source/ATTRIBUTION.md) | 上游文件、适配范围、未复制的第三方素材 |
| [provenance.json](../public/loader-review-v1/source/provenance.json) | 固定提交、原文件 URL 与 SHA-256 |
| [licenses/Codrops-MIT.txt](../public/loader-review-v1/source/licenses/Codrops-MIT.txt) | 核心 JS 的 `Copyright 2014, Codrops`、MIT 文件头及对应许可全文 |
| [licenses/PagePreloadingEffect-README.md](../public/loader-review-v1/source/licenses/PagePreloadingEffect-README.md) | 指定提交原 README 的整合及分发说明 |
| [licenses/GSAP-NOTICE.txt](../public/loader-review-v1/source/licenses/GSAP-NOTICE.txt) | 项目已有 GSAP 的独立许可通知 |
| [vendor/adapted-effects.js](../public/loader-review-v1/source/vendor/adapted-effects.js) | 评审页实际运行的适配代码；作为接入来源，不将演示进度模型带入主首页 |

指定提交没有根目录 LICENSE；上述核心 JS 文件头明确采用 MIT。旧 README 同时允许个人和商业项目整合，并要求不要原样重发、分发或出售；[现行 Codrops 许可页](https://tympanus.net/codrops/licensing/) 声明可下载 demo 默认 MIT，另行说明除外。保留这些不同来源的证据，不将整个旧仓库概括为没有其他条件的 MIT 包。不得移除适配代码的来源及许可通知。原演示的 GraphicBurger 标志、Keyners 浏览器图和上游字体、照片未作为接入资产。

## 真实加载约束

- 进度继续来自生产 [startup-readiness.js](../src/startup-readiness.js) 的实际阶段完成情况：房间与终端 60%、长廊 18%、About 17%、最终准备 5%。这是阶段权重，不是下载字节百分比或计时器。
- 保持已有模型、材质、日夜资源、字体、场景预热及 GPU 完成等待的顺序；只有全部阶段完成且 `finish()` 成功后，才能启动加载遮罩退场并进入 welcome。详见 [STARTUP_PRELOAD.md](./STARTUP_PRELOAD.md)。
- 主首页不得导入评审页的 `DemoProgress`，不得用随机增量、定时累计、固定延迟或动画结束冒充资源就绪。动画缓动只控制呈现，不能推动 readiness gate。
- 未就绪、加载等待或加载失败时保持完整遮挡；失败不能被迟到的成功回调覆盖。保留错误说明、重试和进入/跳过锁定。
- 减少动态使用短淡出或其他低位移呈现，仍等待同一个真实 gate；不得因减少动态而提前露出未准备好的首页。

## 已实现

- [index.html](../index.html) 保留一个加载遮罩及原有可访问性进度/状态/重试钩子，删除原横向加载条的可见呈现；三条 SVG 轮廓使用 `pathLength=100`。`main.js` 只在既有 readiness 回调中把百分比映射为 `strokeDashoffset = 100 - percent` 与标志实体显现比例，不产生任何额外进度。
- 用户通过的 [atelier-orbit-v4.svg](../public/media/brand/atelier-orbit-v4.svg) 使用不对称厚轨道、阶梯切口、四角星核和暖铜光点。依据通过的 AI 概念重新绘制原生 SVG 路径，不使用姓名缩写，不是 Blender 模型或嵌入式位图。制作记录见 [BRAND_MARK_V4.md](BRAND_MARK_V4.md)。加载、终端首页左上、进入房间后的左上标志及 favicon 共用这个资产；历史 review 保留当时的旧标志。
- [cube-intro.scss](../src/cube-intro.scss) 使用不透明墨蓝背景、层叠倾斜轨道、斜向暖光带、轨道地面反射与静态粒纹，标志有局部发光描边、低频铜橙扫光与轨道光点。仅使用 CSS/SVG，没有新增 WebGL 渲染器或字体依赖。
- [cube-intro.js](../src/cube-intro.js) 在真实 `ready()` 后执行标志缩小上移、整片遮幕抬升和原终端欢迎构图进入。为保留既有 QA 接口，内部 `phase` 此时为 `welcome`，另以 `loadingReveal=true` 和 `data-loading-reveal=playing` 明确表示仍在视觉揭幕；揭幕期间进入按钮、跳过、滚轮、点击与 Escape 均锁住。约 1.9 秒后 `loadingReveal=false` / `complete`，恢复原有一次进入逻辑。
- 减少动态取消标志位移及遮幕上升，使用 0.16 秒时间线淡出；CSS 系统偏好与开发 QA 的 `motion=reduce` 都停止扫光/呼吸与描边过渡。揭幕中切换系统减少动态会完成当前揭幕后才解锁；销毁控制器会取消时间线并防止旧完成回调解锁输入。

## 检查与剩余验证

CPU 检查：`scripts/check-startup-loader-c.mjs` **9/9**，`scripts/check-terminal-intro.mjs` **17/17**，`scripts/check-startup-readiness.mjs` **20/20**，历史评审 `scripts/check-loader-review.mjs` **12/12**。新增检查实际执行生产 `main` 的进度回调、真实 readiness、真实 GSAP 与生产 intro controller；DOM 布局、图片解码及 GPU 依然是明确替代，不声称真实渲染通过。旧终端测试的固定 V16 URL 检查更新为实际 release 选择与 compile → fence → finish → ready 顺序，原几何 fixture 仍明确为 V1 terminal / V16 room。

Vite 构建已通过（62 modules；保留已有大体积 JS advisory）。没有通过本页工作更改 Room、材质、烘焙或已批准的 About 文件；本次实现只改加载/UI 与新品牌资产及相应测试文档。

需检查真实加载期间的百分比与遮罩状态、100% 后进入 welcome 的顺序、失败与重试、反复进入或跳过、减少动态，以及手机视口和 resize 下的标志与遮罩位置。切换或销毁时应清理动画回调，避免旧动画隐藏新的遮罩。

既有 `scripts/check-startup-readiness.mjs` 与 `scripts/check-loader-review.mjs` 分别覆盖生产门控的 CPU 行为和历史评审页的模拟行为。它们不能替代主首页浏览器中的 SVG/CSS 呈现、真实 GPU 准备、交互顺序或性能测量。历史评审的 CPU 或浏览器通过也不能直接记为本次 C 主首页接入通过。

历史 crossfold-v3 接入时已在实际主页面检查 1280×720 和 390×844 的加载/欢迎排版；模拟长廊失败时停在真实阶段 60%，重试成功后才显示终端；手机键盘进入完成一次并恢复镜头交互。浏览器日志中的错误均为主动注入的长廊失败，成功页面诊断 errors=[]。证据见 [主页面浏览器检查](validation/loader-c-browser.json)。CPU 全程锁定及减少动态检查与浏览器实测分别记录；未部署。

补充：揭幕中 resize 现在安全完成已就绪的退场，避免旧坐标标志移出视口；ready() 重新读取当前减少动态偏好，并同步 CSS。两项真实控制器回归已加入 9/9 CPU 结果，最终浏览器联检随后执行。

Logo V4 的浏览器验证独立记录于 `docs/validation/logo-v4-browser.json`；上述 crossfold-v3 的截图与记录不可当作 V4 实测结果。
