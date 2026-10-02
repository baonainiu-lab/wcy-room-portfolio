# 作品长廊 V4：连续框墙与实体玻璃

本次按用户要求重构长廊两端框墙、返回门洞和后侧玻璃。继续保留 V3 的清爽场景，没有恢复城市、高架、山体或外围大地台。V1–V3 文件保持；全部 77 个资产 ID、六个展位、馆内小物、植物以及 `gallery.architecture.portal` 返回接口保留。

## 实体建筑

[可编辑源](../assets/blender/works-gallery-v4.blend) 的 `WORKS_GALLERY_V4` 场景保持原太阳、12 盏灯及馆内展品。银色、深蓝、暖金色系延续原场景。

- 两端采用有截面厚度的连续圆角框墙：横向厚 0.44m，环形截面宽 0.36m；背框厚 0.39m、截面宽 0.37m。框墙、背梁、屋梁及右侧低墙实际 Boolean union 成一个闭合连通体，脚部嵌入原地板。
- 门廊为 1.85m 深的独立圆角洞口壳体，和实体门槛连接；保留独立交互 owner。
- 后玻璃分六片，厚 32mm，轮廓裁进真实圆角窗口；顶玻璃为闭合的 30mm 实体，外两片按端框曲线裁成五边形。所有外表面法线朝外，避免原单面顶棚从俯视视角消失。
- 细银色压条、12mm 淡绿玻璃边条和轻微吸收提供可见厚度，没有新增粗黑描边。建筑玻璃与展柜玻璃分别为 `GALLERY_ARCH_GLASS` 和 `GALLERY_CLEAR`。
- 最外两根顶梁缩短至端墙内，外片顶玻璃每侧 696 个采样均未越过后角外轮廓；最小后框余量 6.84cm、端框余量 18.77cm。

[几何检查](../assets/blender/works-gallery-v4/geometry-final-audit.json) 证明统一框墙为 1 个连通组件，0 边界、0 非流形、0 退化面。所有新建实体网格逐个验证闭合；文字是保留的独立字体轮廓，不作为实体墙闭合断言。原薄底座保持，原生地面 Y=-0.88，共同舞台 Y offset=-0.185。

## 准备、烘焙与导出

[准备工程](../assets/blender/works-gallery-bake-v4.blend) 场景为 `WEB_WORKS_GALLERY_V4`。主要模型为 77 IDs、142 nodes、80 meshes/primitives、542976 三角形、6 个运行材质。没有降低馆内原网格或 UV 精度。

| 图集 | 内容 | 尺寸 |
|---|---|---|
| A0 | 重建框墙、门廊 | 4096²，重新展开 |
| A1 | 六个展位 | 4096²，UV 保留 |
| A2 | 家具、灯具、植物、小物 | 4096²，UV 保留 |
| A3 | 原薄底座 | 1024²，UV 保留 |

四张图集均重新烘焙日夜两态，使用真实 Cycles Metal 64 samples、16px 边距、AgX→sRGB。即便保留的展位 UV 没变，也因新墙体和竖梃改变投影而重烘，没有直接复用旧光影。纹理目录为 `public/textures/works-gallery-v4/{day,night}-{0..3}.{png,ktx2}`；UASTC quality2 + Zstd9，完整 mip 链，主图集两态 ASTC/BC7 理论载荷 130.667MiB。

首次跨场景 snapshot 准备发现带 `Object.location` 的箱体和文字变换被非活动场景读取丢失。已修复为先将求值后网格显式转换到世界坐标再保留原 root；新增[源→准备逐点验证](../assets/blender/works-gallery-v4/source-prepared-transform-verification.json)，三个重建 owner 共 29717 个顶点双向比对，最大误差 0.000000267m。框墙和玻璃误差为 0。修复前中间工程及报告归档到 `assets/experiments/works-gallery-v4-before-transform-fix`。因旧准备网格会产生错误遮挡，修复后四图集两态全部重烘。

最终原 GLB 为 `public/models/works-gallery-v4.glb`，压缩 GLB 为 `public/models/works-gallery-v4-compressed.glb`。[导出报告](../assets/blender/works-gallery-v4/export-report.json)、[压缩报告](../assets/blender/works-gallery-v4/compression-report.json)及[完整验证](../assets/blender/works-gallery-v4/pipeline-verification.json)使用同一个修复版 preparation_id `61726e4e5b02b89fd1738685e6a702df8f15a1d19ce9696267266c36bf7e8df3`。原 GLB 为 38,550,188 bytes，SHA-256 `ef6f54192a538afaf5d427c5b04d9c99f22043aff0023439277913da6cb84bbf`；压缩 GLB 为 40,606,824 bytes，SHA-256 `da7f6045703dee51f4ea83f644451293992ba5e2fc7b86a42e41a98779577bbf`。压缩保留 303 个非图片 bufferView 字节、几何及层级。最终重烘白天耗时 240.65 秒，夜间 235.63 秒。

## 玻璃反射与地面投影

新增两个 2048×1024 真实全景反射 capture，日间 32 / 夜间 48 samples。为避免探针正落在新中央竖梃内部，实际 Web 坐标从 `[0,2.7,-3.36]` 微移为 **`[0.12,2.7,-3.36]`**；Blender 为 `[0.12,3.36,2.7]`，相机旋转 `[π/2,0,0]`。仅捕获时隐藏建筑玻璃，保留框墙、展柜、展品和地面，世界使用与网页一致的最新物理日夜天空副本，太阳方向误差 0°。

`public/textures/works-gallery-v4/reflection-{day,night}.{png,ktx2}` 及 [reflection-SOURCE.json](../public/textures/works-gallery-v4/reflection-SOURCE.json) 已包含位置、源哈希、灯光、分辨率及真实渲染记录。KTX2 flipY=false 的方向映射为 `u=fract(.5+atan(webX,-webZ)/(2π))`、`v=.5-asin(webY)/π`。网页使用离线 probe 与 Fresnel，不新增实时反射 pass，实现细节见 [GALLERY_GLASS_V4_WEB.md](GALLERY_GLASS_V4_WEB.md)。

新框墙的地面影子也真实重烘为 `public/textures/gallery-atmosphere-v2/{day,night}.{png,ktx2}`，2048²/64 samples。保持 V1 的细腻中性石材、3 盏局部辅助灯、64m×64m、Y=-0.88、原点中心；KTX2 UV 为 `u=webX/64+.5, v=webZ/64+.5`。源工程为 [gallery-atmosphere-v2.blend](../assets/blender/gallery-atmosphere-v2.blend)，[SOURCE](../public/textures/gallery-atmosphere-v2/SOURCE.json) 与 [COMPRESSION](../public/textures/gallery-atmosphere-v2/COMPRESSION.json) 保存真实渲染及远地线性色采样。天空仍复用 atmosphere-v1，未改原天空文件。

## 复现与验收

脚本位于 `assets/blender/scripts/works_gallery_v4/`。顺序为 `rebuild_architecture.py` → `prepare_v4.py` → `bake_gallery.py --state both` → `export_gallery.py`；CPU 压缩为 `python3 scripts/compress-works-gallery-v4.py --wait --threads 2`。`audit_final_geometry.py` 为只读几何审查。Reflection/ground 脚本不带参数只做 CPU 检查，明确 `--render` / `--bake` 才占 GPU。

`render_v4.py` 只在内存加入背景平面，以原主相机和新增右端/门洞细节相机输出四张 2000×1200、72 samples 实渲图；不保存到源。最终输出目录 `renders/works-gallery-v4/`，主屏轮播应同步真实 `day.png`、`night.png`。最终验证运行 `python3 scripts/verify-works-gallery-v4.py`，包含所有旧模型哈希保护、77 IDs、所有玻璃 NORMAL、两态纹理、probe、ground、最终渲染与 SHA 校验。

最终[白天](../renders/works-gallery-v4/day.png)、[夜晚](../renders/works-gallery-v4/night.png)、[右端细节](../renders/works-gallery-v4/right-end-detail.png)、[门廊背面细节](../renders/works-gallery-v4/portal-detail.png)已实际完成并目视查看，分别耗时 26.69、25.42、24.54、23.32 秒，源哈希均保持。右上外伸小片已消除。门廊主体壳体和门槛为连接体；独立矩形返回背板仍是分离装配件，从背面可见约 5–9cm 缝隙，不声称整个门廊全部零件是一体焊接。完整流水线验证已通过。

最终整体 Web bounds 为 `[-11.1049891,-0.8550000191,-8.1000004]` 至 `[11.1049891,5.4099998474,6.4800000]`。主建筑玻璃节点 `GALLERY_WEB_gallery.architecture.glazing__glass__A0.001` 的 bounds 为 `[-7.285,0.475,-3.482111]` 至 `[7.285,5.190808,-1.285192]`；薄底座护栏玻璃节点 `GALLERY_WEB_gallery.environment.terrace__glass__A1.001` 也使用 `GALLERY_ARCH_GLASS`。节点名中的 A1 为保留历史命名，实际薄底座图集是 A3；透明玻璃本身不进图集。15 个玻璃 primitives 均具备有效单位法线。

网页的路径切换、实际帧率、日夜切换与返回导航由独立浏览器验收记录确认。本版仅供本地预览，用户真实作品及个人资料仍待补充。
