# V13 夜间局部暖光制作记录

状态：V13 夜间局部暖光的完整源、八图集重烘、GLB 导出及连续性验证已完成，并接入本地网站。最终构建通过（20 个模块），网页夜景目视与本轮静置性能采样完成；昼夜切换、显示屏打开作品、Esc 关闭回归已通过，用户尚未最终验收视觉。

方案依据已落盘的 [night_warm_v13.py](../assets/blender/scripts/night_warm_v13.py)和[运行脚本](../assets/blender/scripts/run_night_warm_v13.py)。

## 夜间方案

在已有桌体、窗下架和灯具内增加局部照明，保留冷色夜间环境与深色墙面。脚本以场景线性 RGB 近似 2700–3000 K 暖光；这是颜色设定，不是实测色温，也没有给整幅画面套暖色滤镜。世界环境和曝光不作整体提亮。

| 新增光源 | 位置与意图 | 功率 / 尺寸 / 扩散角 |
| --- | --- | --- |
| `Desk_Underside` | 悬挑工作台下方，照亮运算核心旁的局部地面 | 32 W；0.78×0.075 m；85° |
| `Window_Shelf_Left` | 现有窗下架左段底部，向下形成暖光区 | 22 W；1.35×0.055 m；78° |
| `Window_Shelf_Right` | 窗下架右段底部，补充克制的局部光 | 17 W；0.78×0.055 m；76° |

新增的是嵌入现有结构下方、朝下照射的矩形 Area 光源，不增加可见灯具网格或交互物件。既有 `Floor_Lamp_Practical` 设为 56 W；`Interior_Warm_0 / 1 / 2` 分别设为 34 / 32 / 22 W；展示龛 `L_Niche_*` 改为约 3000 K 的颜色设定并将功率上限限制为 34 W。既有小灯、环灯和架内发光材质复制为夜间专用材质，发光强度分别为 1.05 或 1.8。

## 已完成流程与文件

1. `save_sources()` 读取 V12 完整源，将暖光配置应用于夜景，并另存 `assets/blender/orbital-atelier-v13.blend`；白天场景保留。另存 `orbital-dual-bake-v13.blend` 准备工程，使用包含着色信息的指纹检查几何、UV 与法线一致，写出 `dual-bake-v13-preparation.json`。
2. 运行脚本的 `--preview` 分支先准备源文件，再执行 1,100×807、28 采样且启用降噪的 Blender 夜景预览，目标为 `renders/night-warm-v13-preview.png`。
3. 完整流程先复制 V12 贴图到 `public/textures/lighting-v13/`，再对夜间图集 0–7 全部重烘；白天图像不重烘。进度写入 `assets/blender/night-warm-v13-status.json`。
4. 导出目标为 `public/models/orbital-atelier-v13.glb`。最后逐张比较 V12 / V13 的 `*day*.png` SHA-256，全部相同才记录 `dayByteIdentical: true` 与 `phase: complete`。

完整夜烘约 415 秒，状态为 `complete`。V13 保留 37 个室内根资产、93 个室内 ID 和 2 个外部 ID，373,203 三角形、100 个绘制图元、10 张内嵌图像。暖光进入既有图集，不新增网页实时灯光、可见几何、图元或图集分配。

| 交付 | 大小 / SHA-256 |
| --- | --- |
| 完整源 `orbital-atelier-v13.blend` | 73,860,523 字节；`2469222a77fc326d34223785a15675cf1abf65ecdf6c9297ca2619d9d9f16d17` |
| 准备工程 `orbital-dual-bake-v13.blend` | 82,918,553 字节；`70eafb513a0ea7b2f369e568892f9ef9b6f4486936871f5803e980771aff62d0` |
| 网页模型 `orbital-atelier-v13.glb` | 46,178,184 字节；`44178b2372dfb4978da24fb6910c0d279bc353a9ed4936656fb52d45e18824f9` |

依据：[交付报告](../assets/blender/night-warm-v13-delivery.json)、[烘焙状态](../assets/blender/night-warm-v13-status.json)、[资产校验](../renders/asset-validation-v13.json)。

## 已完成核验与网页待检

[GLB 连续性检查](../renders/night-warm-v13-continuity-check.json)通过：100 个网格的几何 / UV / 法线 / 索引及 195 个节点的层级与变换和 V12 精确一致；8 张日间图集、日景窗图共 9 张 PNG 哈希相同，夜景窗图也未改。[源日景核验](../assets/blender/source-day-v13-verification.json)涵盖 2,097 个对象及变换、网格、材质节点、灯光、世界节点和视图设置，V12 / V13 签名一致，仅场景改名。

[实际 Blender 夜景](../renders/lighting-v13-night-blender.png)及[指定图像区域对比](../renders/night-warm-v13-image-check.json)已留档。同一 1,500×1,100 镜头下，桌下地面区域平均图像亮度 8.80→34.24、窗下地面 26.60→84.03，后墙区域 11.71→10.99。它们是选定栅格区域的统计，不能替代全场景光度、所有角度或用户审美验收。

本地网页夜景目视检查已完成：局部暖光池清楚可见，墙面仍冷暗；[调整前](../renders/night-warm-v13-before-web.png)与[调整后](../renders/night-warm-v13-after-web.png)截图留档。昼夜切换、显示屏打开作品、Esc 关闭回归已通过。

最终 `pnpm build` 通过（20 个模块），CSS 20.39 kB（gzip 5.03 kB），JavaScript 1,123.60 kB（gzip 345.60 kB），仅有常规 bundle 大小提示。[本轮性能报告](../renders/performance-night-warm-v13.json)与[原始快照](../renders/performance-night-warm-v13-samples.json)记录 844×795、DPR 2 的夜间静置画面 51.12 秒 / 8 次快照，Blender 已停止，无活跃悬停或面板，截图用前 6 秒排除。FPS 中位数 120.4819，帧间隔 P95 为 9.8–10.2 ms，GPU P50 / P95 为 2.764–3.049 / 4.268–5.625 ms，CPU P95 为 1.0–1.2 ms；104 次绘制、375,079 个渲染三角形，37 / 93 资产统计，`errors: []`。短时样本的 `stable120Verified` 仍为 `false`，不宣称稳定 120 FPS。

仅本地制作与预览，个人资料仍待补充，角色暂不接入；不修改旧项目、不上传或部署。最终夜景视觉仍须用户验收。

本轮整合后的[浏览器检查记录](../renders/night-warm-v13-browser-check.json)与[日景截图](../renders/night-warm-v13-day-web.png)已保存；本地预览最终停留在夜间模式。
