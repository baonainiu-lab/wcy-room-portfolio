# 展厅 V1 字体覆盖核验

日期：2026-09-24。

正式字体沿用用户选定的寒蝉圆黑体 Heavy，派生名为 **Atelier Rounded Display**，原生 OS/2 字重 **900**。新展厅使用同一正式 WOFF2，没有为缺字引入另一套显示字体。

本次从原 TTF 补齐 30 个字符，保留上一版全部 510 个字符。新增字符：

`–←↔仍位具册切占厅场安完实屉意或换推摆暂未此浏真笼继览车预`

覆盖核验包含 `index.html`、`src/main.js`、`src/scene-callout.js`、`src/gallery-navigation.js`、`src/works-gallery.js` 中全部中文、中文标点、相关排版标点/箭头和可打印 ASCII。包括“日光长廊”“返回房间”“作品展位”“归档抽屉”“陈列画册”“暖光灯笼”等实际文案。所需字符在原字体和最终子集的 cmap 中均存在，缺字数为 **0**。

## 实际产物

- 文件：`public/fonts/orbital-rounded/atelier-rounded-display-ui.woff2`
- 字符：540；glyph：797；文件：104,264 bytes。
- SHA-256：`67c9f01efec8c819e926a896fa89e46b0dfb5abf00a94e5b767b5cd9f89b21bb`。
- 上一版 SHA-256：`9c1ecdc6cb0a42ed16519a1e31788757d1233933be1acee18924b532a6ab2d5b`。
- 原 TTF SHA-256：`8e008ecec9854ec2887cea9e28a7826c65c00409d532e0fe5bd01afe704e718e`。
- 字符清单：`public/fonts/orbital-rounded/CHARACTERS.txt`。
- 字符、新旧哈希及来源快照：`public/fonts/orbital-rounded/SOURCE.json`。

## 轮廓与许可核验

从原始 `ChillRoundGothic_Heavy.ttf` 重新生成子集，使用 fontTools 4.65.0 和 WOFF2 压缩。解压最终 WOFF2 后，以 `DecomposingRecordingPen` 逐字比较全部 **540** 个 cmap 字符的完整绘制指令，同时逐字比较 hmtx 字宽/侧边距：轮廓差异 **0**，度量差异 **0**。未扩张轮廓或添加假粗。

最终字体 name 表与上一版派生字体逐条完全一致，保留 Atelier Rounded Display / Heavy、唯一名和 PostScript 名；原版权、OFL 许可与许可链接记录保持不变。`OFL.txt` 和 `NOTICE.txt` 未修改。原 TTF 未修改。

fontTools 仅安装在项目 `tools/fonttools`，没有修改系统 Python 环境。新增字体仍使用现有 URL，浏览验收时需刷新页面以加载新的 WOFF2。
