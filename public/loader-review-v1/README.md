# 开场动效验收 V1

本地打开 `/loader-review-v1/index.html`。在该完整地址后追加 `#A` / `#B` / `#C` / `#D` 可直达指定方案，例如 `/loader-review-v1/index.html#C`。所有运行资源均来自本地；放在 Vite `public` 内，可以原样拷贝至构建输出，不依赖 `/src` 开发服务器路径。

2026-10-01：用户已选择 **C「标志升起」**，主首页适配、新标志及真实进度绑定已完成，浏览器验收由主任务记录。A/B/C/D 四个历史方案仍保留在此页供回看；本页继续使用模拟进度和当时标志。主首页接入及验证状态见 [LOADER_C_INTEGRATION.md](../../docs/LOADER_C_INTEGRATION.md)。

| 方案 | 动画来源 | 完整编排 |
| --- | --- | --- |
| A 斜线启幕 | Olaf / gsap-website-reveal-animation | 45° 填充 → 墨蓝字幕 → 铜橙横向色幕 → 首页 |
| B 折页开场 | Codrops / PageLoadingEffects · Origami | 标志与进度 → 菱形折页向外展开 → 首页 |
| C 标志升起 | Codrops / PagePreloadingEffect | 本站标志轮廓描边 → 标志缩小上移 → 整幕抬起 → 首页 |
| D 为你开窗 | Codrops / PageLoadingEffects · Frame it | 四边进度 → 中心矩形开窗 → 首页 |

来源、原始许可、固定提交和适配差异见 [source/ATTRIBUTION.md](./source/ATTRIBUTION.md)，原文件哈希见 [source/provenance.json](./source/provenance.json)。未采用原作者的个人素材、图片和字体。当前 GSAP 3.15.0 原样复制项目已安装版本；没有安装依赖。

## 操作

- 点击 A/B/C/D 自动播放；键盘方向键也可切换方案。
- 重播从 0 开始；暂停可停住加载或退场。
- 拖动进度会暂停模拟，100% 才开始退场；从完成或退场拖回小于 100% 会恢复完整加载遮罩。
- 模拟等待从新一轮开始，在 78% 停住；取消勾选后继续。
- 模拟失败从新一轮开始，在 62% 停住；“重试演示”取消失败选项再播放。
- 减少动态默认跟随系统；可手动切换。该模式取消大幅位移与变形，仅用短淡出。
- 沉浸预览在浏览器支持 Fullscreen API 时可用；移动端可正常上下滚动查看控件。

所有数字都只是演示进度。首页目标使用本站历史截图并标注为示意，不代表最新材质效果。本页自身未接入 Three.js、Blender 或正式场景预加载，也不承担主首页加载功能；已选 C 的主首页版本使用真实 readiness gate 并单独复验。

## 检查

```sh
node scripts/check-loader-review.mjs
```

2026-10-01：12 项 CPU 检查通过；review.js 与 adapted-effects.js 语法检查通过。实际 GSAP core 用于路径字符串插值检查；浏览器的 SVG attribute、CSS、绘制、键盘及移动端行为不由这个 CPU 检查代替。

浏览器操作均走真实按钮/滑块。可只读 `script#loader-review-diagnostics` 的 JSON 确认阶段、百分比、方案、遮罩可见性与图片就绪状态。诊断每 100ms 或状态变化更新，无隐藏操作 API。评审页的浏览器验证由主任务另行记录；这些检查不能替代 C 接入真实主首页后的浏览器、GPU 或性能验证。
