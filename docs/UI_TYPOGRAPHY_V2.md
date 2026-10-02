# UI 字体与文字动效 V2

用户要求：**“ui字体换一个换一个有艺术感点的字体 字体加粗加点动效”**。本次保留已批准 UI V1 的布局，只调整展示文字的字形、字重和反馈动效。

## 字体设计

- “创作空间”、加载页标题、内容面板标题：中文宋体风格，字重 **700**。较粗的竖画与收笔给暖灰金属界面增加印刷、铭刻的质感。
- 顶部作品 / 关于 / 联系、底部白天 / 夜晚、场景物件名称：相同展示字体，字重 **650**。
- 说明、正文、提示保留系统无衬线；副标题 500。长文与小字号不会全部变成密集衬线。
- 窄屏 320 px 的品牌标题仍为 16 px，字距减至 .065 em；标志与导航保留原来的独立触摸区域。

## 本地字体、来源和许可

来源为 [Google Fonts 的 Noto Serif SC](https://github.com/google/fonts/tree/main/ofl/notoserifsc)，官方元数据列出其 [Noto CJK 上游](https://github.com/notofonts/noto-cjk)、字体来源提交 `985fa52c81c1d6692ccdd82bc3656e8fb932fd89`。核查日期：2026-09-22。

[官方 OFL 1.1 许可](https://github.com/google/fonts/blob/main/ofl/notoserifsc/OFL.txt)允许修改、嵌入和随软件再分发，须保留版权和许可，不能将字体单独出售。原许可原样保存在 `public/fonts/orbital-editorial/OFL.txt`，保留字体 name 表中的原版权与许可；项目 MIT 许可没有变更。本地子集不宣称由原字体作者为本网站创作或背书。

原文件 `NotoSerifSC[wght].ttf`：25,125,512 bytes，SHA-256：

```text
050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9
```

本地派生文件 `public/fonts/orbital-editorial/orbital-editorial-sc-ui.woff2`：**188,964 bytes（184.5 KiB）**，SHA-256：

```text
e79e72d9ffe6beec7fc755bc3518bae5df6a1ec595bf2c4c9a671aaaf5b40004
```

FontTools 4.65.0 将 `index.html`、`src/main.js`、`src/scene-callout.js` 中现有中文字符、标点和基本 ASCII 做成 **497 字符 / 910 字形**子集；保留布局特性，将变量字重范围限制到 **600–700**，以 WOFF2 发布。所有请求字符均受原字库支持，没有缺字。为清楚区分修改版本，派生 family / PostScript name 重命名为 `Orbital Editorial SC` / `OrbitalEditorialSC-UI`，原版权、许可、设计者等 name 记录保留。

- `public/fonts/orbital-editorial/SOURCE.json` 保存逐文件来源链接、上游与派生文件哈希。
- `public/fonts/orbital-editorial/UPSTREAM-METADATA.pb` 保存官方元数据。
- `public/fonts/orbital-editorial/CHARACTERS.txt` 保存当前完整子集字符。
- 浏览器只读取本地 WOFF2，并使用 preload、`font-display: swap`；没有 Google Fonts 运行时请求。
- 后续新增资料文字时可更新子集；当前子集外字符回退至系统宋体。正文不受子集覆盖限制。

## 动效

- 加载页“创作 / 空间”两组字依次上移 7 px 并淡入，持续 650 ms，间隔 75 ms。
- 进入房间后，用原流程移除 `inert` 的时机启动品牌文字、导航和昼夜文字的一次性入场。动效只作用于内部文本，不接管 GSAP 外层 `.preview-ui` 的 opacity / transform。入场使用 `animation-fill-mode: backwards`，结束后释放文本 transform，避免覆盖后续悬停与焦点反馈。
- 导航悬停：字面上移 2 px；短线由中心伸展。按下：97% 轻压缩。
- 昼夜标签悬停上移 1 px，按下轻压缩；选中太阳 / 月亮有小角度旋转。镜头复位按钮悬停也以轻微反向转动反馈。
- 物件提示名称悬停上移 1 px；弹出面板标题以同一节奏进入。
- 全部为事件触发的有限过渡，没有循环发光、背景滤镜、字距逐帧变化或新增 JS 动画循环。
- `prefers-reduced-motion` 下取消位移反馈和延迟，入场即时完成。

## 验证

- `src/style.scss`、`src/scene-callout.scss` 均由项目 Sass 成功编译。
- FontTools 重新打开 WOFF2 校验：497 个字符全部有 cmap 映射，版权 name 记录仍存在。
- DOM 原 IDs、data 属性、ARIA 和交互入口保留；只增加文字 span 与本地 preload。
- 浏览器已在 844 px 默认宽度及 320 px 窄视口实测：标题字重 700、导航 650，展示字体成功接入。
- 320 px 视口无横向溢出；品牌右缘为 123 px，导航左缘为 166 px，两者间距为 43 px。
- 导航焦点反馈实测为 `translateY(-2px)`，下划线伸展至 `scaleX(1.3)`；入场结束后反馈仍正常生效。
- 上述为桌面浏览器视口检查，不代表实体手机测试。与 V13 灯光整合后的最终完整构建通过（20 个模块，CSS 20.39 kB / gzip 5.03 kB），仅有常规 bundle 大小提示；[本轮性能记录](../renders/performance-night-warm-v13.json)已保存，用户最终视觉验收仍待完成。
