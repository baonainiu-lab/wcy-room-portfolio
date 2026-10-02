# V14 金属边沿与走线精度

本轮针对窗框、墙顶、展示柜框和平台侧沿的烘焙亮边。问题主要来自这些细长表面在旧图集中被切得过碎、分到的像素少；没有增加全屏模糊或后期描边。

## Blender 改动

在 V13 网页预处理工程里，将建筑与平台边沿的既有面拆分到局部 Atlas 8，连续条带展开并重新烘焙昼夜 3072² 贴图。曲面法线、几何位置、三角面与独立资产结构保留。图集打包留 32 px 间距，烘焙边缘扩展 16 px。

| 区域 | 当前约纹素 / 米 | 相对 V13 |
| --- | --- | --- |
| 窗框、窗槽光条、平台精密边 | 221 | 2.24–2.33 倍 |
| 墙顶与立柱 | 192 | 约 1.95 倍 |
| 平台侧沿 | 207 | 约 2.3 倍 |

旧 0–7 图集和窗景共 18 张 PNG 哈希保持一致，不降低原有大面的纹素密度。UV 检查无折叠绕序、无退化 UV 三角形；完整数值见 [UV 报告](../assets/blender/edge-atlas-v14-report.json)。

## 当前交付

- 网页模型：`public/models/orbital-atelier-v14.glb`，49,383,384 字节。
- SHA-256：`a933ce1ba865c5ad5293e11bfac51ad082f8c1522ff828ad89d45aa17bd5e232`。
- 完整材质 / 灯光源：`assets/blender/orbital-atelier-v14.blend`。
- 实际网页 UV 工程：`assets/blender/orbital-dual-bake-v14.blend`。
- 双态贴图：`public/textures/lighting-v14/`，0–8 加独立 window；运行时共有 10 个昼夜混合材质。

`src/dual-lighting.js` 自动读取实际图集编号，窗景使用单独的字符串槽位，避免和新增 Atlas 8 冲突。外景夜间压暗继续只作用于 Atlas 5 / 6。

## 校验与成本

模型仍为 373,203 三角形，绘制图元 100 → 102；37 个室内根资产、93 个室内 ID、2 个外景 ID 保留。导出数值有限、索引有效，局部变换和层级保持。见 [导出校验](../renders/edge-precision-v14-export-check.json)和[完整交付记录](../assets/blender/edge-precision-v14-delivery.json)。

新图集使每种灯光状态的纹素增加 8.257%；双态 RGBA8 加完整 mipmap 的理论额外纹理内存约 96 MiB，实际以设备格式和驻留情况为准。三角形没有增加。网页默认视角为 106 次绘制 / 375,079 个渲染三角形，含外部装饰与提示。

实际 GLB 贴图检查图：[白天](../renders/edge-precision-v14-day-unlit.png)、[夜晚](../renders/edge-precision-v14-night-unlit.png)。这些是 Blender 读取真实导出 GLB 的无光照渲染，不是网页截图；网页抗锯齿与交互另见 [预览检查](PREVIEW_CHECK.md)。

地板细管接缝、地毯和休闲椅缝线沿用原几何。本轮改善指定金属边沿的贴图连续度，不代表全场所有细线都完成重构；远景低于一个屏幕像素的细线仍可能出现锯齿。最终视觉等待用户反馈。
