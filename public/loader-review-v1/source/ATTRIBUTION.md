# 创作空间 · 开场动效适配 V1

这是本地视觉验收页，入口 `/loader-review-v1/index.html`，C 方案直达地址为 `/loader-review-v1/index.html#C`。四种方案共用本站已有首页截图；进度由独立演示模型产生，不是下载进度，该评审页没有调用生产 `startup-readiness.js`。

2026-10-01：用户已选择 **C「标志升起」**，主首页适配和 CPU 检查已完成，浏览器验收由主任务记录。四个历史方案及其来源记录继续保留；评审页的模拟运行与主首页真实加载分开记录。详见 [LOADER_C_INTEGRATION.md](../../../docs/LOADER_C_INTEGRATION.md)。

## A · 斜线启幕

- 上游：[Olaf / gsap-website-reveal-animation](https://github.com/olaf-wilkosz/gsap-website-reveal-animation/tree/5fc869e418af5b7df8baece5032df16483773f5b)
- 提交：`5fc869e418af5b7df8baece5032df16483773f5b`
- 已实际读取：`script.js`、`style.css`、`index.html`、`README.md`、`LICENSE`。
- 直接适配 `loader-wrapper` 的 45° 填充条、`loader-text .letter` 的逐字进入、`revealer` 横向遮盖再退出的 GSAP 编排。
- 原许可：MIT，Copyright (c) 2023 Olaf。原始全文保留在 [licenses/olaf-MIT.txt](./licenses/olaf-MIT.txt)。上游 README 声明其练习来自 [Codegrid 教程](https://www.youtube.com/watch?v=ki-22rwwn3A)，本记录保留这项制作来源；不声称本页是作者官方版本。
- 改动：原固定 `delay` 改为进度达到 100% 才执行的单一时间线；缩短节奏；使用本站标志、字体、墨蓝/米白/铜橙；删去原照片、字体、个人文案与远程资源。

## B · 折页开场 / D · 为你开窗

- 上游：[Codrops / PageLoadingEffects](https://github.com/codrops/PageLoadingEffects/tree/d4348fe750a3903d962775f76b77fc41d203b0d4)
- 提交：`d4348fe750a3903d962775f76b77fc41d203b0d4`
- 已实际读取：`js/svgLoader.js`、`css/component.css`、`index12.html`（Origami）、`index4.html`（Frame it）、`README.md`。
- 直接适配：上述 HTML 的复合路径轮廓与 `SVGLoader.hide()` 的路径退场机制。B 为狭缝展开成菱形，D 为中心点展开成矩形窗口。
- 改动：把路径统一成相同的绝对命令供现有 GSAP 插值，使用 `evenodd` 挖空；替换 Snap.svg 的动画调用；增加进度展示、取消、重播、移动端及减少动态支持。没有复制 Snap.svg、classie、原网页、图片或字体。

## C · 标志升起

- 上游：[Codrops / PagePreloadingEffect](https://github.com/codrops/PagePreloadingEffect/tree/7a7893f4145f1dcfcf5dccd1ec893b24170fc987)
- 提交：`7a7893f4145f1dcfcf5dccd1ec893b24170fc987`
- 已实际读取：`js/pathLoader.js`、`js/main.js`、`css/effect1.css`、`index.html`、`README.md`。
- 直接适配 `PathLoader` 的 `getTotalLength()` / `strokeDashoffset = length * (1 - progress)`，以及 `effect1.css` 的加载元素退去、品牌缩小上移、整片 header 上移和内容进入的分层序列。
- 改动：将原随机进度替换为统一演示状态机；本站标志轮廓代替原圆环及作者示例 logo；CSS keyframes 转成可取消的 GSAP 时间线；没有复制 GraphicBurger 标志、Keyners 浏览器图或任何上游字体/图片。

## Codrops 许可证据与适配范围

两个指定提交均没有根目录 LICENSE。上述核心 JS 原文件头明确写明 `Copyright 2014, Codrops`、`Licensed under the MIT license` 并链接 MIT。对应文件头、按其链接保存的 MIT 正文见 [licenses/Codrops-MIT.txt](./licenses/Codrops-MIT.txt)。这不是声称上游存在该名称的原始 LICENSE 文件。

两个旧 README 同时允许个人/商业项目整合，要求不要原样重发、分发或出售；原 README 分别保留在 [PageLoadingEffects-README.md](./licenses/PageLoadingEffects-README.md) 和 [PagePreloadingEffect-README.md](./licenses/PagePreloadingEffect-README.md)。[现行 Codrops 许可页](https://tympanus.net/codrops/licensing/) 声明可下载 demo 默认 MIT，另行说明除外。本页采取适配整合方式，只保留有用的动画逻辑/路径并替换演示内容，未打包原站演示或原素材。

## 本地依赖及项目素材

- `vendor/gsap.min.js`：原样复制本项目**已经安装的 GSAP 3.15.0** `node_modules/gsap/dist/gsap.min.js`，保留原始版权文件头；未安装或升级 npm 依赖。GSAP **不是 MIT**，独立受 [GSAP Standard License](https://gsap.com/community/standard-license/) 约束，许可链接及通知见 [licenses/GSAP-NOTICE.txt](./licenses/GSAP-NOTICE.txt)。此页是四个固定效果的本地验收展示，不是动画制作或导出工具。
- `media/terminal-homepage-demo.png`：原样复制本站 `renders/terminal-only-homepage.png`，属于历史首页截图；只作为统一揭幕目标，标注“本站已有画面 / 示意”，不代表当前材质最终效果。
- 标志：本站 `/media/brand/atelier-fold-v2.svg`。
- 字体：本站 `/fonts/orbital-forge/atelier-forge-display-ui.woff2` 和系统字体，未复制原作者字体。
- 所有运行所需资源均为本地路径。上游链接只供点击查看；无外部 CDN、iframe、统计或远程字体请求。

完整提交、被读取文件及 SHA-256 位于 [provenance.json](./provenance.json)。`vendor/adapted-effects.js` 是实际运行的适配源码，不是只写“灵感来自”的原创替代品；页面布局、控制器及演示状态机为本次项目实现。

## 未采用的候选

[MohamedEzz524 / Experiment-3-cinematic-landing-page-reveal](https://github.com/MohamedEzz524/Experiment-3-cinematic-landing-page-reveal/tree/412ad6667172d11ac721e2c44e5b004b22f250e4) 的 README 与 package.json 有 MIT 声明，但该提交完整归档没有 LICENSE/COPYING/NOTICE，也缺独立许可全文与著作权署名。依本轮明确许可筛选要求未直接复制其代码或素材。这不是断言它完全没有许可声明。

## 验证范围

`scripts/check-loader-review.mjs` 做 CPU 检查：模拟进度 gate、等待/失败/恢复、拖动重播、实际 GSAP 核心对规范化路径字符串的插值、描边算法、来源与本地资产完整性。SVG DOM attribute 绑定、实际视觉与动态播放由浏览器验证，CPU 检查不代替它们。这个演示没有加载 Three.js / WebGL，不证明生产首页性能；已选 C 方案还需与真实 startup gate 集成后复验。

浏览器验证通过真实 A/B/C/D 按钮、重播、进度滑块、等待/失败复选框及减少动态进行。只读 DOM 节点 `script#loader-review-diagnostics` 每 100ms 或状态变化时更新 JSON，包含阶段、模拟百分比、方案、等待/失败/减少动态选项、遮罩可见性及示意图就绪状态；没有隐藏的操作 API。
