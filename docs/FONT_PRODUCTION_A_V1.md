# A「抖音美好体 Bold」生产接入

用户在 V4 字体验收中选择 A，截图中的立体厚度处于开启状态。正式首页欢迎语、姓名占位、页头品牌、导航、弹窗、物件标题以及长廊导航标题现统一使用该字体。正文、说明和时间读数保留原有清晰字体。

没有接入待批准的背景概念，没有修改 main.js、模型、相机或动画时间线。原有逐字入场、悬停动作和文字厚度阴影保留。

## 文件与命名

- 字体：`public/fonts/orbital-forge/atelier-forge-display-ui.woff2`
- 内部名称：`Atelier Forge Display`
- 样式：normal；CSS face 与标题使用 700；`font-synthesis: none`
- 来源：[ByteDance 官方字体仓库](https://github.com/bytedance/fonts)，提交 `327565b61501d7a6d4902ed6ce417a7bd2ae54e6`
- 许可：[上游 SIL OFL 1.1](https://github.com/bytedance/fonts/blob/main/DouyinSans/OFL.txt)，完整副本、版权和 NOTICE 随字体保留。

上游文件名及样式名为 Bold，但 OS/2 `usWeightClass` 实际是 400。此次保留该原始元数据和真实轮廓，在 CSS 中把这份唯一 Bold 字面明确映射到 700，不进行浏览器合成加粗，也不将它误写成“上游原生 700 元数据”。

使用独立内部 family/full/PostScript/unique 名称，避免保留字体名称冲突。继承验收版本的修复：移除上游损坏的可选 GSUB 表，其余字形坐标、正常字符映射及字宽保留。详见同目录 SOURCE.json。

## 覆盖与验证

生产子集扫描 `index.html` 和全部 `src/**/*.js`、`src/**/*.scss` 共 39 个源文件，包含 main.js 中动态个人资料、物件名称、长廊说明、开场与错误提示，也保留上一版字符集合及 printable ASCII。

- 当前源文件出现的汉字：507 个，缺字 0。
- 实际网页子集：634 个字符，66,008 字节。
- 634 个字符逐字比较源字体与输出字体的 glyf 坐标、hmtx 字宽：均一致。
- 原始版权和许可 name records：均保留。
- `–`、`↔`、`↗`、`・` 四个上游缺失的非汉字符号保留现有系统回退，不伪造字形。其中 `・` 仅出现在动效诊断标签中。
- SHA-256：`481862c1bcfdf9b1b224c366229e83dd1324f01eac6eea38903da363ddcd67c4`。

构建及覆盖校验脚本：`assets/font-candidates/v4/build-production.py`。

```sh
PYTHONPATH=tools/fonttools /Users/a90/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python assets/font-candidates/v4/build-production.py
```

验证记录：`assets/font-candidates/v4/production-validation.json`。SOURCE 与报告记录所有扫描源文件哈希；以后新增标题汉字须重新生成子集。

SCSS 接入范围：`style.scss`、`cube-intro.scss`、`gallery-navigation.scss`、`scene-callout.scss`。统一采用 `--font-display-weight`，去掉此前仅适合寒蝉 Heavy 的 900 声明。`index.html` 的 preload 指向新文件。保留旧字体文件供历史方案核查，但正式首页不再预加载或引用旧 family。

主任务负责检查桌面与手机的实际字形、换行、阴影和进入房间后的标题。字体改动不会替代此前模型与交互的独立验证。
