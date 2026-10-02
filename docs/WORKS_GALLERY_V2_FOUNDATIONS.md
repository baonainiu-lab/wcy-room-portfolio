> 历史记录：V2 已被用户要求的精简长廊 V3 替代。当前模型和接入见 [WORKS_GALLERY_V3.md](WORKS_GALLERY_V3.md)；以下环境结构及坐标属于旧版。

# 作品长廊 V2：闭合城市地台与承重结构

用户反馈长廊背景没有底部、整体悬空。本轮只修复环境承接，保留原长廊展品、灯光、返回门接口和 86 个原有资产 ID。未加入新作品内容或第三方素材，未修改旧项目或发布网站。

## 原因和修复

V1 可编辑源中 `Urban landscape base` 是渲染背景，并标记 `export_exclude`。网页资产因此缺少地面；37 根城市与高架支柱在 Blender Z=-5.34/-5.91 处截断，三道远景长平台没有下部支柱。

V2 删除该不可导出的背景平面，添加一个非交互环境根 `gallery.environment.foundation`。其下包含 123 个可编辑部件：连续的闭合城市土地、近馆实心台基、后侧花园平台及阶梯挡土台、37 个原支柱基础、30 根远平台承重柱及其柱脚和横梁。所有新增部件只在其共同环境 owner 内合并为一个网页网格，不合并任何馆内交互对象。

土地顶面为 Z=-5.82，底面实测为 Z=-7.6199998856。新增网格具有 0 边界边、0 非流形边、0 松散顶点、0 零面积面。原 86 个 ID、层级、几何及 UV 指纹完全保留。新源灯光参数与 V1 一致，未改变展品。

## 当前资产与贴图

- [可编辑源](../assets/blender/works-gallery-v2.blend)，场景 `WORKS_GALLERY_V2`。
- [烘焙准备源](../assets/blender/works-gallery-bake-v2.blend)，场景 `WEB_WORKS_GALLERY_V2`。
- [原 PNG GLB](../public/models/works-gallery-v2.glb)：35,353,208 bytes。
- [网页 KTX2 GLB](../public/models/works-gallery-v2-compressed.glb)：37,353,148 bytes，SHA-256 `366fcec8eead92040255ea7321a897d42723dd1e7a25fe18e1ca60602bebc66c`。
- 162 节点、90 网格 / primitives、6 材质、834070 三角形、87 个唯一资产 ID。比 V1 增加 1 个 primitive、48548 三角形。
- 五组图集尺寸：4096 / 3072 / 4096 / 4096 / 2048，材质 `GALLERY_LIGHTMAP_0` 至 `GALLERY_LIGHTMAP_4`，另保留玻璃材质。独立 PNG 与 KTX2 位于 `public/textures/works-gallery-v2/{day,night}-{0..4}`。
- A1 城市保持原 UV，重新烘焙与基础的接触光影；A4 专用于新增基础。两态均实际执行 Cycles Metal、64 samples、16px 边距。实测 A1/A4：白天 45.97/29.21 秒，夜晚 32.94/25.01 秒。
- A0/A2/A3 原建筑与馆内贴图逐字节保留，manifest 明确记录其原 preparation ID 与几何 UV 证据，未声称它们重新烘焙。
- UASTC quality 2 + Zstd 9、完整 mip 链。压缩模型保留全部 258 个非图片 bufferView 字节及几何层级；双态 ASTC/BC7 理论有效载荷约 162.667 MiB。实际格式和帧率由浏览器另行验收。

## 网页坐标和共同场景接入

Blender 到网页为 `(x,y,z) → (x,z,-y)`。模型整体 Web bounds 为 `[-60,-7.6199998856,-84]` 至 `[56,16.7645988464,28]`；镜头构图应继续依据馆内建筑，而不是扩大后的环境边界。

原生长廊中的额外无限地面应位于 Y≤-7.62，避免切掉闭合底座。共同场景若沿用房间 ground Y=-1.065，应采用 gallery offset.y=4.755，使城市土地**顶面**与房间地面齐平，并隐藏共同场景专用副本内的原无限地面。早期底面齐平 offset.y≈6.555 的建议已废弃：宽城市土地会覆盖房间区域，使用该值会把房间低处埋入土地。

## 检查与复现

- [几何与承接检查](../assets/blender/works-gallery-v2/foundation-verification.json)、[坐标与闭合检查](../assets/blender/works-gallery-v2/prepared-bounds.json)、[流水线验证](../assets/blender/works-gallery-v2/pipeline-verification.json)。
- [导出报告](../assets/blender/works-gallery-v2/export-report.json) / [压缩报告](../assets/blender/works-gallery-v2/compression-report.json)。V1 源及两个旧 GLB 校验值未变化。
- 三个角度为真实 Cycles 24 samples / 1200×820 检查图：[总览](../renders/works-gallery-v2/day-foundation-overview.png)、[台基低机位](../renders/works-gallery-v2/day-podium-low.png)、[城市侧面](../renders/works-gallery-v2/day-city-supports.png)。已目视检查承接连续、无截断悬空支柱；不等同于穷尽任意相机位置。
- 顺序执行 `assets/blender/scripts/works_gallery_v2/build_prepare_foundations.py`、`bake_foundations.py`、`export_gallery.py`；最后运行 `python3 scripts/compress-works-gallery-v2.py --wait`。检查脚本 `verify_foundations.py` 与 `render_foundation_review.py` 为只读，不保存修改到源文件。
