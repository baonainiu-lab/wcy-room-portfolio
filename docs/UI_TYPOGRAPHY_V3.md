# UI 字体 V3 · 寒蝉圆黑体立体厚字

2026-09-24：作品长廊接入时已将正式子集扩展到540字符，当前校验值及新增30字见 [字体补齐记录](FONT_GALLERY_V1.md)。下文510字符与旧hash为原V3发布时记录。

2026-09-22，用户明确选择“**寒蝉圆黑体立体厚字**”。已把候选 02 的原生 Heavy 字形与立体厚字效果接入正式本地 UI；字体方向已选定，主站最终视觉仍待反馈。主站预览：[127.0.0.1:5173](http://127.0.0.1:5173/)。

## 字体文件与覆盖

当前展示字体是寒蝉圆黑体 Heavy 的本地派生子集，family 为 `Atelier Rounded Display`，原生字重 **900**，`font-synthesis: none`。根页面预加载及 `@font-face` 均指向 `public/fonts/orbital-rounded/atelier-rounded-display-ui.woff2`，不依赖在线字体服务。

- 文件 99,512 字节，510 字符、767 字形，SHA-256 为 `9c1ecdc6cb0a42ed16519a1e31788757d1233933be1acee18924b532a6ab2d5b`。
- 在验收页子集基础上加入 `↗`（U+2197），覆盖当前 `index.html`、`src/main.js`、`src/scene-callout.js` 的文案字符；必需字符、子集字符缺失均为 0。
- 510 个字符的轮廓与原字体一致，未伪造加粗；源字体 Version 3.700，12,870,060 字节。后续添加新文案时，按 `CHARACTERS.txt` 重新核对子集。
- [SOURCE.json](../public/fonts/orbital-rounded/SOURCE.json) 保存原文件、下载地址、字重、覆盖验证及派生哈希；[OFL.txt](../public/fonts/orbital-rounded/OFL.txt) 随字体保留。

## 正式 UI 表现

首页标识、加载标题、面板标题、顶部导航、昼夜标签、进入按钮与物件标题采用新字形。正文与说明继续使用系统无衬线字体，避免长文也承受展示字体的高笔画密度。

夜晚的大标题使用暖米白字面和多层深金属色侧面；白天的大标题改为深蓝灰字面，搭配由浅灰过渡至蓝灰的侧面。厚度来自 CSS 多层 `text-shadow`，不是三维文字模型。导航、昼夜标签及物件标题使用较浅的侧面阴影；物件提示仍以覆盖场景的可读性为主。加载页保留深色背景和暖米白厚字。

主品牌标题桌面 26 px，随现有断点缩至 23 / 19 / 16 px；加载标题 41 px，窄屏按原布局缩小；面板标题 32 px，手机为 27 px；导航 15 px，窄屏 14 / 12 / 11 px；物件标题 13 px，600 px 以下为 12 px。以上采用真实 900 字重，大小不同而非使用伪粗体。

既有文字分组入场、导航悬停抬起、按压反馈与控制按钮动效保留，`prefers-reduced-motion` 规则保留。未重新改动 UI 结构、房间灯光、模型、镜头与小资产交互。`src/main.js` 的 UI revision 现为 3；V13 场景和角色暂不接入状态保持。

## 构建与检查边界

本轮 `pnpm build` 通过：20 个模块；CSS 21.49 kB（gzip 5.33 kB），JS 1,123.60 kB（gzip 345.60 kB）。构建保留常规大 chunk 提示。字体文件大小和 SHA-256 已核对。

正式站浏览器 QA 已完成，证据为 [ui-typography-v3-browser-check.json](../renders/ui-typography-v3-browser-check.json)：

- 844 × 795 的加载标题、夜景主站、日景主站与日景关于面板已目视检查；计算样式为 `Atelier Rounded Display / 900`，夜晚暖侧面、白天灰侧面以及导航、昼夜标签、物件标题的轻立体阴影均核对。
- 320 × 640 日景页面 `scrollWidth` 为 320，无横向溢出；品牌右界 123.171875 px、导航左界 166 px，未重叠。
- 静音进入、昼夜切换、关于面板打开与关闭正常，检查当时控制台 warn / error 为空。主站已恢复 844 × 795 夜晚预览。

以上为桌面浏览器视口模拟。此次未重新测量帧率，不宣称稳定 120 FPS。字体选择已经批准，最终接入效果仍待用户视觉反馈。

## 来源与历史

上游为 [ChillRoundGothic](https://github.com/Warren2060/ChillRoundGothic)，[具体许可](https://github.com/Warren2060/ChillRoundGothic/blob/main/License.txt) 为 SIL Open Font License 1.1。派生文件已重命名主 family / full / PostScript / unique 名，保留原版权、许可及原生字重；字体继续按 OFL 分发，不归入模板 MIT。原始字体与候选资料仍保存在 `assets/font-candidates/v3/chill-rounded-heavy/`。

[五款字体验收页](FONT_REVIEW_V3.md) 保留作选型依据；[V2 字体记录](UI_TYPOGRAPHY_V2.md) 保留为历史，不代表当前主站。此次仅本地实现，不修改旧项目、不推送仓库、不部署域名。
