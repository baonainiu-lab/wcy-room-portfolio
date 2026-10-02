# 关于我 · 档案工坊 V3

用户选择了 A 方案，并明确要求「就按照这个建模吧还原灯光以及贴图材质」。其后补充「场景不要做太小了」。本版已经制作实际 Blender 模型、材质与灯光。用户随后明确要求「接入到网站」，现已接入新项目的本地预览；这项接入授权不等同于另行确认离线渲染通过。本轮本地网页视觉与交互检查已完成，未部署或上传。

## 文件与验收图

- [可编辑 Blender 源文件](../assets/blender/about-atelier-v3.blend)
- [建筑围合修订 V2](../assets/blender/about-atelier-v3-architecture-v2.blend)
- [建筑修订远景](../renders/about-atelier-v3-architecture-v2/wide.png)
- [建筑修订近景](../renders/about-atelier-v3-architecture-v2/hero.png)
- [完整场景](../renders/about-atelier-v3/hero.png)
- [奖项与柜体近景](../renders/about-atelier-v3/awards.png)
- [工作台近景](../renders/about-atelier-v3/desk.png)
- [皮革座椅近景](../renders/about-atelier-v3/chair.png)
- [原批准概念图](../renders/about-photoreal-v3/a-archive-atelier.png)
- [几何、资源与构图审查](../assets/blender/about-atelier-v3-audit.json)

## 实际制作

以斜切角石质地台组织左侧胡桃木档案柜、独立抽屉与内部收藏物、木竖条屏、三件占位奖项及薄壁玻璃罩、深蓝工具挂板、钢木工作台、联系终端、曲面画册、材质册与量具、桌下书档与工具箱、带缝线的皮革转椅、画册架与植物。抽屉、收藏舱、展品、工具、书册等保留独立稳定根节点和原始变换，未合并成一件不可交互的大网格。

主场景实际边界约 **7.53 × 5.03 × 4.15 米**。验收主镜头中主体覆盖 **84.84% 画面宽度、88.71% 画面高度**，四周保留完整边缘。此结果来自实际几何投影计算；网站接入后仍需按设备宽高比重新适配相机，不能直接把离线镜头作为移动端或网页缩放范围。

主场景含 128 个资产根节点，127 个带交互标记。离线源经评估约 57.22 万三角形；网页派生模型为 430,574 个三角形，保留全部资产 ID 和独立层级。网页点击已连接奖项、技能、个人资料和联系方式面板；这不表示每个资产都有独立内容，未提供的个人信息仍为「待补充」。不作稳定 120 FPS 承诺。

## 贴图与光照

胡桃木、棕色皮革、水磨石与织物采用真实 2K PBR 贴图，颜色、粗糙度、细微凹凸独立控制。木材按面分别进行三平面采样，修正柜前/桌面旋转 BOX 映射退化为单向采样的问题。金属使用原创微表面材质；玻璃罩为实际 4 mm 闭合薄壳，透射 1、IOR 1.46，并在筒壁底部增加支撑环防止法线插值造成整段镜片式畸变。

日光由定向暖太阳、真实湖景 HDRI、奖项与工作台局部暖光组成。窗框投射斜向阴影；建筑低铁玻璃使用直通阴影近似，保留相机与反射光线的真实透射，避免玻璃阴影把室内直接日照完全阻断。湖景使用 HDRI 环境，并非可漫游的远山几何；室内窗框、地砖、支柱、地毯与背景植物是独立模型。

主图为 Cycles 128 samples、2400 × 1600；三个近景为 1800 × 1500。没有用概念图充当 Blender 渲染，没有把 AI 概念画面贴成场景模型。实际引用的 12 张 PBR 图片与 1 张 HDRI 已打包进源文件。

## 检查与边界

- 调整奖项台与桌角间距；错开奖项，避免主视角互相遮挡。
- 修正柜顶盆栽与书堆、前盆与画册架、书册承托和地台底部支撑。
- 座椅扶手采用平滑曲线与圆润封口，收细皮革缝线；桌面几何习作改为平底承托。
- 独立资产 ID 唯一；无非有限几何、无零面积三角形；无丢失外部图片。
- 用户奖项、具体技能和联系方式继续标记「待补充」。抽象奖项、图形和样本不代表真实成绩或履历。
- 本地接入依据为用户明确要求「接入到网站」，没有修改旧项目 `/Users/a90/Documents/wcy90-portfolio`，没有部署或上传。
- 当前记录区分几何/自动化检查、浏览器实测与用户艺术验收；浏览器检查通过不代表用户已认可全部视觉细节。

## 本地网站接入

[本地预览](http://127.0.0.1:5173/) 中，从沙发旁茶几上的书册进入「关于我」。使用现有 Blender 书册资产 `notebook`，平面尺寸放大至原来的 1.4 倍，厚度放大至 1.2 倍；下层 `creative_folio` 平面放大至 1.34 倍。笔与旋钮调整到茶几上的空余位置，书册保持承托关系，模型顶点与 UV 未重建。机器人不再作为「关于我」入口。

工坊在共用转场舞台的左侧（X = −34），作品长廊保留在右侧（X = +34）；工坊地台上的实体返回接口连接原房间。主体按真实模型顶点适配相机，建筑背景不计入主体构图，避免为了包含整面玻璃墙而把桌台缩得过小。

网页主体使用 [压缩 GLB](../public/models/about-atelier-v3-compressed.glb)（41,100,996 字节），另有未压缩回退文件。四张 4096 × 4096 的 Cycles COMBINED 日光烘焙图采用 KTX2 UASTC + Zstd 和完整 mip 链；已烘焙表面关闭二次色调映射，玻璃和金属保留实时环境反射。网页派生文件没有改写源 `.blend`，原 SHA-256 仍为 `d7a9ec353e8214201c586e823283259c64f63a99f8284913d8aff94c691a2b40`。

初次导出漏掉的建筑环境已恢复到独立 [建筑 GLB](../public/models/about-atelier-v3-architecture.glb)。用户进一步指出切镜远景中立柱粗糙后，新增真实 Blender 建筑修订 V2：顶高由 7.25 米降低到约 5.63 米，补齐 L 形顶部石梁、窗台、柱帽/柱脚、金属接缝、内退压条和 7 段暖色嵌灯。23 个竖向结构逐个核对顶部、底部连接，前面和右面保持开放。

原来约 24.5 × 14 米的薄地砖区域收为约 13.31 × 11.36 米的完整亭体基座；20 块地砖由约 0.466 米厚的闭合石材台身承托，外沿盖板、黑色内退封底和黄铜边线形成连续收口。98 个建筑源对象保留为单独可编辑对象；网页端仅建筑不透明部分合并，8 片原玻璃独立保留。建筑使用一张额外的 4K Cycles 烘焙图，原家具参与遮挡及反弹光计算；背景植物、长凳、地毯不加入此次网页建筑导出，也不保留它们的烘焙阴影。主体模型与 128 个资产 ID 保持不变。

窗外使用既有 Lake Pier HDRI 的 [AgX 日景全景图](../public/textures/about-atelier-v3/landscape/lake-pier-day.png)，同一 HDRI 提供环境反射。网页将全景与反射统一转向开阔水面及远岸，去掉倾斜视角；它是全景背景，并非可漫游的湖岸模型。

三个场景共用同一个 60 秒昼夜时钟。工坊主体四张与建筑一张 4096 × 4096 夜景贴图由 Blender Cycles 64 samples 真实烘焙，完整保留日景 UV。台灯、奖项局部暖灯、建筑烘焙与玻璃金属反光同步变化；窗外使用同一朝向的夜景派生图。日出、日落分别持续约 15 秒，切入、返回与尺寸变化不会重新启动时间。底部时间继续隐藏，开场仍固定日光。

夜景源文件：[主体](../assets/blender/about-atelier-v3-night-bake.blend)、[建筑](../assets/blender/about-atelier-v3-architecture-night-bake.blend)；[实际 Cycles 夜景预览](../renders/about-atelier-v3-night/night-wide.png)。窗外夜景由内置 imagegen 基于已有 CC0 日景图片编辑光照，实际分辨率为 1774 × 887，保留 2:1 比例；不是新增 HDR 实拍。提示词与来源见 [夜景生成记录](../assets/scene-backdrops-v1/about-night-prompt.json)。

## 接入验证记录

- [主体导出报告](../assets/blender/about-atelier-v3-web/export-report.json)、[压缩报告](../assets/blender/about-atelier-v3-web/compression-report.json)：128 个资产 ID、原始层级/坐标、四张 4K 图及源文件哈希。
- [建筑源验证](../assets/blender/about-atelier-v3-web/architecture-v2-source-validation-report.json)：98 个闭合正体积网格、23 个竖向结构的上下连接、所有地砖/外沿与承重台身接合；原主体几何、变换和资产 ID 不变。另有[网页建筑验证](../assets/blender/about-atelier-v3-web/architecture-validation-report.json)；建筑不参与点击或主体构图。
- [全景派生记录](../assets/blender/about-atelier-v3-web/landscape-preview-report.json)：同一 HDRI、AgX 色调映射和原许可，无新增第三方图片。
- [转场检查](validation/gallery-transition-v4.json)：30/30；[主体构图检查](validation/about-framing-v3.json)：3/3，覆盖 9 种宽高比。这些为自动化验证，不替代浏览器视觉检查。
- 书册调整已检查 16 个承托边角与邻近物体间距；浏览器实测 824×795 与 390×844，昼夜端点与中间状态同步、5 张 4K 夜景 KTX2 加载成功、书册左侧进入与实体返回后控制恢复，无场景错误。汇总状态见 [本地接入记录](validation/about-web-integration-v3.json)。

## 来源

几何由本项目在 Blender 中原创制作；字体为未修改的 DouyinSans Bold，保留原 OFL。真实 PBR 与湖景环境使用核实后的 CC0 资源，具体作者、官方链接、原文许可和文件哈希见 [贴图来源](../assets/textures/about-atelier-v3/README.md)、[湖景记录](../assets/textures/about-atelier-v3/landscape/manifest.json)。现有模板许可证保持原样。

重建与渲染脚本：[about_atelier_v3](../assets/blender/scripts/about_atelier_v3)。
