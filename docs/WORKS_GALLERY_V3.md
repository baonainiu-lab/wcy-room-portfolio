# 作品长廊 V3：仅保留长廊

用户最新要求“把作品展示的场景后的那些都删除吧，只保留长廊设计”，覆盖此前 V2 扩展环境的方向。V3 从 V1 另存精简副本：移除城市、高架、山体和外围植物，不引入 V2 的宽地台、实心高台及基础支柱。V1、V2 源及模型均保留，文件哈希验证未改变。

原长廊框架、玻璃、门廊、薄底座、六个作品展位、馆内植物、灯笼、画册、推车及全部独立交互层级保留。`gallery.architecture.portal` 继续作为返回接口，用户真实作品资料仍待补充。

## 源、模型和贴图

- [可编辑源](../assets/blender/works-gallery-v3.blend)，`WORKS_GALLERY_V3`；[准备源](../assets/blender/works-gallery-bake-v3.blend)，`WEB_WORKS_GALLERY_V3`。
- [原 GLB](../public/models/works-gallery-v3.glb)：26280380 bytes，SHA-256 `ca1774effb1061080f62cbad523b9f7cfba077b158f8767fc964fc350b18b3b8`。
- [网页压缩 GLB](../public/models/works-gallery-v3-compressed.glb)：28314580 bytes，SHA-256 `186fff1b46292fc17628062124aa43e7f3d691921ccfef9e8cd2bc436ad3ee67`。
- 77 个唯一资产 ID、142 节点、80 网格 / primitives、560890 三角形、5 材质。
- 删除 ID：`gallery.environment.city`、`gallery.environment.plant.00` 至 `.07`；相对 V2 另删除 `gallery.environment.foundation`。保留 `gallery.environment.terrace`，它是长廊自身薄底座。
- 当前四组图集尺寸为 **4096 / 4096 / 4096 / 1024**，位于 `public/textures/works-gallery-v3/{day,night}-{0..3}.{png,ktx2}`。材质仍为 `GALLERY_LIGHTMAP_0..3`，另有透明玻璃材质。

| V3 图集 | 内容 | 来源 |
|---|---|---|
| A0 | 原长廊建筑与门廊 | V1 A0，日夜 PNG 字节保留 |
| A1 | 六个展位及作品占位 | V1 A2，日夜 PNG 字节保留 |
| A2 | 馆内家具、植物、灯具和小资产 | V1 A3，日夜 PNG 字节保留 |
| A3 | 长廊薄底座及其护栏 | 新建独立 UV，1024² 日夜真实烘焙 |

V1 城市图集和 V2 基础图集完全不进入 V3。薄底座实际执行 Cycles Metal 64 samples、16px 边距，白天 8.88 秒、夜晚 6.30 秒。压缩采用 UASTC quality 2 + Zstd 9 与 mip 链，保留 228 个非图片 bufferView 字节及几何、层级。双态 ASTC/BC7 理论有效载荷约 130.667 MiB；实际浏览器帧率需单独测量。

## 几何、灯光与地面

薄底座实体闭合，0 边界边、0 非流形边，原底面完整保留。Web bounds 为 `[-11.1049891,-0.8550000191,-8.1000004]` 至 `[11.1049891,5.4116578,6.4800000]`。原生场景地面使用 Y=-0.88；共同场景可使用 Y offset=-0.185，对房间 Y=-1.065 地面保留约 0.025 间隙。横向排布与转场由网页实现处理。

140 个馆内三维采样点沿原太阳方向查询删除环境的 BVH，检测到的环境直射遮挡为 0。保留资产的网格、UV 以及原三组图集像素未变化，灯光参数保持原样。原贴图含 V1 环境的间接反弹贡献；删除远景后可能存在细微间接光差异，因此未声称全局光照数学完全一致。本轮按用户希望快速查看精简效果，保留已采用的馆内光影，仅为薄底座重新烘焙。

## 实际渲染与验证

[白天 PNG](../renders/works-gallery-v3/day.png) / [夜间 PNG](../renders/works-gallery-v3/night.png) 均为 2000×1200、Cycles Metal 72 samples，沿用 V1 相机 `(17,-28,15.5)`、57mm，分别耗时 22.52 / 22.50 秒。两张图已目视检查，无城市、高架、山体、外围植物。仅加入未保存、未导出的纯色渲染地面 Y=-0.88，匹配网页舞台；本轮没有修改房间窗外城市。它们用于同步房间主屏的长廊轮播图，具体接入由网页资源流程处理。

验证产物：[删除和底座检查](../assets/blender/works-gallery-v3/deletion-verification.json)、[直射光影响检查](../assets/blender/works-gallery-v3/lighting-impact-audit.json)、[导出报告](../assets/blender/works-gallery-v3/export-report.json)、[压缩报告](../assets/blender/works-gallery-v3/compression-report.json)、[最终流水线验证](../assets/blender/works-gallery-v3/pipeline-verification.json)、[实渲染记录](../renders/works-gallery-v3/render-final-both.json)。

复现顺序：`assets/blender/scripts/works_gallery_v3/prepare_gallery_only.py` → `bake_terrace.py` → `export_gallery.py` → `python3 scripts/compress-works-gallery-v3.py --wait`。`render_gallery_only.py` 不保存修改到源文件。最终只读校验运行 `python3 scripts/verify-works-gallery-v3.py`。

## 网页接入

`src/works-gallery.js` 已切换 V3 GLB、77 IDs 和四组 KTX2，背景几何从导出模型中真实删除，不再依赖隐藏节点。浏览器四组图集实际解码为 ASTC。场景实体门框保留返回，连续三维切镜见 [V3 切镜记录](SCENE_TRANSITION_V3.md)。主屏两张长廊轮播也已换成本版日夜实渲染，2000×1200、11 mip、sRGB，来源与校验值位于 `public/textures/live-room/SOURCE.json`。

当前浏览器检查记录位于 `renders/works-gallery-v3/web-verification.json`。用户真实作品仍待补充，当前只在本地预览。
