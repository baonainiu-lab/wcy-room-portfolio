# 字体候选验收 · V3

记录日期：2026-09-22。最新状态：**用户已选择“寒蝉圆黑体立体厚字”（02），现已接入正式本地 UI V3，最终视觉仍待反馈。** 见 [正式接入记录](UI_TYPOGRAPHY_V3.md)。下文保留选型阶段的候选与验收页检查记录。

用户先反馈“不够艺术啊 这个不就是楷体吗 去找一个艺术点的”，随后要求“多找几种字体让我验收 还有字体要有厚度”。本页先提供真实字体的字形、笔画与立体阴影对比；后续用户以“寒蝉圆黑体立体厚字”明确选择了候选 02 及立体厚字效果。

## 本地对比页

打开 [5 款字体对比页](http://127.0.0.1:5173/font-review-v3/index.html)。页面文件为 `public/font-review-v3/index.html`、`review.css`、`review.js` 和 `candidates.json`；必须使用包含 `index.html` 的完整地址。

五款字体均由本地 WOFF2 加载。页面每款使用相同的“创作空间”“作品 / 关于 / 联系”“在这里，记录创作与想象”作比较，并可放进夜景静态排版预览。字体卡片和预览按钮只切换本页样式，不会提交选择或替换主站。

夜景底图 `public/font-review-v3/room-night.png` 是本项目 `renders/night-warm-v13-after-web.png` 的逐字节副本，2,433,231 字节，SHA-256 为 `c38007f50ba4edb9ce534d39aec191247e95c1bb520512d1e0b89031cd6a9acc`。它用于比较文字与房间风格，不是新增渲染，也不承担实时房间交互。

## 候选顺序与真实字重

| 编号 | 上游字体名称 | 字形方向 | CSS / 原生字重 | 网页子集字节 | 派生 family |
| --- | --- | --- | ---: | ---: | --- |
| 01 | 标小智无界黑 | 极粗宽扁 · 金属字块 | 400 | 38,588 | `OrbitalReviewBlock` |
| 02 | 寒蝉圆黑体 Heavy | 厚实圆角 · 饱满雕塑感 | 900 | 82,120 | `Atelier Rounded Display` |
| 03 | 寒蝉无机体·宽体 | 横粗竖细 · 展览美术字 | 500 | 87,184 | `Atelier Reverse Display` |
| 04 | 得意黑 | 倾斜切角 · 动势标题 | 400 | 34,160 | `OrbitalReviewSlant` |
| 05 | 站酷庆科黄油体 | 圆角切口 · 未来铭牌 | 400 | 18,508 | `Room Review Qingke` |

五份 WOFF2 合计 **260,560 字节**。无界黑和得意黑属于原生单字重设计，400 不表示无界黑的笔画细；圆黑 Heavy 为原生 900。无机体的特征是横粗竖细，不作为均匀极粗黑体描述。得意黑保留原生倾斜字形，CSS 使用 normal，不再叠加假斜体。页面使用 `font-synthesis: none`，保留字体原有字形，不通过描边或浏览器合成字重伪造笔画。

## 厚度与排版

“平面字形 / 浅浮雕 / 立体厚字”三档使用 CSS `text-shadow` 展示不同的侧面厚度，默认立体厚字。这是二维文字的视觉效果，不是真实三维文字网格；平面档便于单独判断字体本身。小号导航和控制条采用更浅的阴影，减少字腔被阴影干扰。

大字样本桌面使用 `clamp(36px, 5.8vw, 72px)`；520 px 以下为 `clamp(40px, 11vw, 60px)`。卡片导航为 17 px，700 px 以下为 15 px。夜景品牌标题为 28 px，700 px 以下 22 px，520 px 以下 18 px。上述字号均来自当前验收页 CSS，不是正式网站字体参数。页面保留窄屏布局和减少动态偏好规则。

## 来源、许可与派生文件

所有候选均使用 SIL Open Font License 1.1。具体原文件、下载地址、版权、版本、原始及派生哈希保存在 `assets/font-candidates/v3/<id>/SOURCE.json`；网页字体旁附对应许可。子集的主 family / full / PostScript 名已改为表中派生名称，保留版权与 OFL；页面展示的上游名称用于识别来源，不表示原作者为派生版本背书。

- **标小智无界黑**：[https://github.com/maoken-fonts/unbounded-sans](https://github.com/maoken-fonts/unbounded-sans)；[上游许可](https://github.com/maoken-fonts/unbounded-sans/blob/v1.100/OFL.txt)；[来源记录](../assets/font-candidates/v3/unbounded/SOURCE.json)；[随附许可](../public/fonts/review-v3/unbounded/LICENSE.txt)。网页文件 `public/fonts/review-v3/unbounded/review.woff2`，SHA-256 `eb8ad1ab8d2856f84decc2345a6905cb620b023dd74e2633b94b2d906adc74e9`。
- **寒蝉圆黑体 Heavy**：[https://github.com/Warren2060/ChillRoundGothic](https://github.com/Warren2060/ChillRoundGothic)；[上游许可](https://github.com/Warren2060/ChillRoundGothic/blob/main/License.txt)；[来源记录](../assets/font-candidates/v3/chill-rounded-heavy/SOURCE.json)；[随附许可](../public/fonts/review-v3/chill-rounded-heavy/OFL.txt)。网页文件 `public/fonts/review-v3/chill-rounded-heavy/display.woff2`，SHA-256 `e1d95e36642c28dacb9d55d70908943d008d3f28f46e4f74d1815c50ff0f3416`。
- **寒蝉无机体·宽体**：[https://github.com/Warren2060/ChillTanHei](https://github.com/Warren2060/ChillTanHei)；[上游许可](https://github.com/Warren2060/ChillTanHei/blob/main/License)；[来源记录](../assets/font-candidates/v3/chill-tanhei/SOURCE.json)；[随附许可](../public/fonts/review-v3/chill-tanhei/OFL.txt)。网页文件 `public/fonts/review-v3/chill-tanhei/display.woff2`，SHA-256 `de5ef451a916e209df8f997c4ee691275e7576eae41abe9cc9bb6b22b95adb2a`。
- **得意黑**：[https://github.com/atelier-anchor/smiley-sans](https://github.com/atelier-anchor/smiley-sans)；[上游许可](https://github.com/atelier-anchor/smiley-sans/blob/v2.0.1/LICENSE)；[来源记录](../assets/font-candidates/v3/smiley/SOURCE.json)；[随附许可](../public/fonts/review-v3/smiley/LICENSE.txt)。网页文件 `public/fonts/review-v3/smiley/review.woff2`，SHA-256 `9d541f59dc4ddf6a23bf079c22a63171fe2896a5aa7b467c42514d57b7569178`。
- **站酷庆科黄油体**：[https://github.com/googlefonts/zcool-qingke-huangyou](https://github.com/googlefonts/zcool-qingke-huangyou)；[上游许可](https://raw.githubusercontent.com/google/fonts/main/ofl/zcoolqingkehuangyou/OFL.txt)；[来源记录](../assets/font-candidates/v3/zcool-qingke/SOURCE.json)；[随附许可](../public/fonts/review-v3/zcool-qingke/OFL.txt)。网页文件 `public/fonts/review-v3/zcool-qingke/review-qingke.woff2`，SHA-256 `678dbc1c1ca0f0b1a7a64c9de8cebc29afe7c413e8bda5c056129b9d0cef7aeb`。

候选字体经过字符子集化和 WOFF2 转换，字形轮廓与原生字重保留。无界黑、得意黑各含 293 个子集字符；两款寒蝉字体各含 509 个；黄油体为当前样本所需的 128 个。后续选定字体并接入完整 UI 前，须依据当时实际文案重新核对子集覆盖，尤其不能直接把黄油体当前的样本子集当作全站完整字库。

## 选型阶段与后续批准

- 对比页制作时，主站尚保留 UI V2 的 `Orbital Editorial SC`，用户已否定其视觉风格；当时未修改主站、场景或角色接入状态。
- 用户现已明确选择候选 02（`chill-rounded-heavy`）与 `extruded_text_shadow`。正式 UI V3 已使用扩展到 510 字符的独立子集，实际文件与效果见 [UI_TYPOGRAPHY_V3.md](UI_TYPOGRAPHY_V3.md)。其余四款仍保留为比较材料。
- 选型批准不等于正式接入效果已最终验收；以下 QA 只对应独立候选页。
- 所有工作仍限于本地，不推送仓库、不部署域名；原模板 MIT 许可与场景、性能历史记录保留。

## 本轮检查范围

主任务完成本地浏览器检查：844 × 795 与 390 × 844 两个视口均无横向溢出，五款卡片的字形已目视核对；卡片 03 可切换到对应场景预览，场景快捷按钮 02 可切换字体；平面模式的计算 `text-shadow` 为 `none`，浅浮雕计算样式及立体厚字模式也已检查。390 px 宽的场景控件无重叠，检查当时控制台 warn / error 为空。页面现恢复默认视口、01 字体及立体厚字模式，并回到候选对比页开头。

`node --check public/font-review-v3/review.js` 通过。本轮只新增独立静态验收页，未运行新的生产构建；以上不替代正式字体接入后的检查，也不构成稳定 120 FPS 的证明。这段检查发生在正式接入前；现已收到候选 02 的选择，正式 UI QA 另见接入记录。
