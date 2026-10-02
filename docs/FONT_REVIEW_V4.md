# 游戏岗位作品集：标题字体验收 V4

本地入口：<http://127.0.0.1:5173/font-review-v4/index.html>。

首轮只增加独立验收页。用户随后明确选中 A「抖音美好体 Bold」，截图开启立体厚度；现已据此接入生产标题，实施与覆盖证据见 [FONT_PRODUCTION_A_V1.md](./FONT_PRODUCTION_A_V1.md)。其余候选仍仅用于比较，V3 页保持原样。没有虚构姓名、项目、岗位经历。

## 四款真实字体

| 选项 | 上游字体 | 视觉用途判断 | 一手来源 |
| --- | --- | --- | --- |
| A | 抖音美好体 Bold | 饱满切角、硬表面与科幻标题 | [ByteDance 官方字体仓库](https://github.com/bytedance/fonts) |
| B | 站酷快乐体 | 不规则手作块面、风格化与独立游戏 | [Google Fonts 官方项目](https://github.com/googlefonts/zcool-kuaile) |
| C | 荆南波波黑 Bold | 波浪笔画、厚重卡通与玩具感 | [作者授权发布仓库](https://github.com/maoken-fonts/KNBobohei) |
| D | 得意黑 | 前倾窄字、速度感；保留为旧方案对照 | [atelierAnchor 官方仓库](https://github.com/atelier-anchor/smiley-sans) |

前三款为 V3 之外的新候选。视觉用途是本项目设计判断，不能视为字体作者背书。

KNBobohei 仓库 README 明确由荆南字坊授权发布，附委托书链接。采用该仓库实际提供的 1.710 版本；没有将第三方网站的更高版本号误标到此文件。

## 字形与厚度

- 大标题、侧边短句及四列样张均为浏览器 `@font-face` 加载的真实文字。背景概念图仅作小幅配色参考，不用于伪装字体字形。
- 每款使用原生字形和原生字重，不使用 CSS 合成加粗；`font-synthesis: none`。
- “立体厚度”仅切换 CSS `text-shadow`，可以查看无厚度的平面原字形。
- 同时比较“创作空间／游戏美术／我的作品／开始探索”，同文案、同字号。
- 页面支持移动端重排、键盘按钮、可见焦点和减少动态效果。当前候选在实际字体载入后显示状态，失败会明确提示。
- 浏览器诊断写入 `#font-review-diagnostics`，包含每款 `loaded`、实际样张宽度、选项和错误列表。

## 来源及许可记录

原文件保存在 `assets/font-candidates/v4/`，来源仓库使用 shallow sparse clone，固定提交记录在每款 `SOURCE.json`。得意黑复用此前下载并核验的官方 v2.0.1 原文件。

四款均使用 SIL OFL 1.1：

- [抖音美好体 OFL](https://github.com/bytedance/fonts/blob/main/DouyinSans/OFL.txt)
- [站酷快乐体 OFL](https://github.com/googlefonts/zcool-kuaile/blob/main/OFL.txt)
- [荆南波波黑 OFL](https://github.com/maoken-fonts/KNBobohei/blob/main/OFL.txt)
- [得意黑 OFL](https://github.com/atelier-anchor/smiley-sans/blob/v2.0.1/LICENSE)

网页子集使用新内部名称 `Atelier Forge Display`、`Atelier Playcut Display`、`Atelier Bouncy Display`、`Atelier Slant Display`。family/full/PostScript/unique 等名称均已修改，避免使用原字体保留名。版权和许可信息原样保留在字体内及同目录 `OFL.txt`、`NOTICE.txt`。

抖音官方 v1.01 TTF 的 GSUB 内存在无效 lookup/subtable 偏移，fontTools 不能解析该表。此次将损坏的可选 GSUB 替换表移除，再进行子集与 WOFF2 转换。正常字符映射、字形轮廓和字宽不改，修复已写入对应 SOURCE/NOTICE。此版本是明确改名的 OFL 衍生网页子集，不冒称未经修改的原版。

钉钉进步体排除：已下载的官方法律声明第 4 条禁止未经授权上传发布字体文件，以及修改／转换字体。因此只保留原文件于非公开研究目录 `assets/font-candidates/v4/dingtalk/`，未拷贝到 public，未作为网页字体候选。

## 验证

构建脚本：`assets/font-candidates/v4/build-review.py`。

```sh
PYTHONPATH=tools/fonttools /Users/a90/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python assets/font-candidates/v4/build-review.py
```

构建时逐字验证所有必需样张字符均存在，并比较原文件和输出文件的 glyf 坐标，确认轮廓不变。每款子集 176 个字符；文件体积依次为 12,492／10,992／18,304／16,160 字节，总计 57,948 字节。

已检查 review.js 语法；HTML、CSS、JS、字体元数据、背景缩略图和四个 WOFF2 经本地服务器均返回 HTTP 200。四个文件内容 SHA-256 与 SOURCE 记录一致。

浏览器实际渲染与交互由主任务继续验收；不得将静态 HTTP 检查写成已完成视觉验收。
