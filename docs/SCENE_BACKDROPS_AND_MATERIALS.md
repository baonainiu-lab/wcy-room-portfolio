# 场景背景与材质更新

当前本地预览采用三个独立风格的环境，共用同一个 60 秒昼夜时钟；没有新增手动切换或底部时间显示。

## 背景

- 房间：蓝灰色科技园区，日间金属建筑和植被，夜间琥珀色窗光。
- 长廊：海湾美术馆、远岸城市与山体，日景及相同构图的夜景。
- 关于我：既有 Lake Pier 日间环境与对应夜景光照编辑，保留原建筑围合。

房间与长廊图片由内置 imagegen 生成，日夜文件各为 **1774×887**；路径为 `public/media/scene-backdrops-v1/`。提示词：[日景](../assets/scene-backdrops-v1/prompts.json)、[夜景](../assets/scene-backdrops-v1/night-prompts.json)。图像来源及哈希：[SOURCE.json](../public/media/scene-backdrops-v1/SOURCE.json)。关于我夜景路径与提示词：[生成记录](../assets/scene-backdrops-v1/about-night-prompt.json)。

长廊全景采用连续的半角 atan 经度映射，将原生图像像素优先分配到主要观看方向；中心水平角采样密度为原来的 4 倍，垂直参数为 1.7。此调整没有增加图片的原生分辨率。全方向仍有定义，没有将图片裁成有限扇区；昼夜共享完全相同的投影。原生视图和切镜舞台共用采样方式，极俯视不会因扇区边缘夹取而拉出长条。背景保持景深感，前景为独立真实模型。

[投影检查](../output/gallery-panorama-coverage-audit.json)覆盖 9 种视口、243 组平移/缩放和 54 个作品聚焦视图。网页已查看日夜外观、极俯视与缩远旋转；这些检查不代表所有视角都经过人工验收。

## 房间 V16 材质与开场

房间现用 `orbital-atelier-v16-compressed.glb`，精修 33 个钛金属、石墨涂层、陶瓷与织物材质，保留原配色、几何、UV、法线、层级和变换。采用世界位置与世界法线的显式三平面采样；织物输入为已核验的 CC0 扫描，其他微表面为项目原创。

实际完成 **24 张昼夜图集与 3 张开场接收面图集，均为 Cycles 96 samples**，开场与正常光照来自同一个 V16 prepared 源。窗口和屏幕保留原内容及动态切换。模型 71,018,672 bytes、413,855 个三角形，几何缓冲与 V15 逐字节一致。

导出有 95 个资产 ID，网页仍有 **92 个可交互组件、37 个逻辑根节点**：两个外景 ID 分离到环境，原终端四个子部件替换为终端 V2 的三个独立子部件。V15/V16 经相同运行时配置后的组件集合完全一致。

- [资产、哈希与烘焙记录](../assets/blender/photoreal-materials-v16-release.json)
- [79 项 CPU 检查和组件集合回归](validation/room-materials-v16-cpu.json)
- [实际本地浏览器检查](validation/room-materials-v16-web.json)：开场单次触发、日间进入、接收面恢复并释放、昼夜同步、书本进入关于我及实体返回、长廊载入通过。仅覆盖报告中的视口与代表状态，不是逐帧人工验收。

本批 V16 派生及烘焙在最新“优先使用 Blender MCP”偏好之前，以真实 Blender 后台脚本与 Cycles 完成。此次接入只更新网页引用并通过 MCP 只读核对连接，没有改动当前打开的其他 Blender 项目；不能将历史后台烘焙记为本轮 MCP 建模。后续新建模遵循最新偏好。未新增稳定 120 FPS 测试，历史 V15 性能记录保留原版本归属。

## 长廊 V5 材质

替换石材、棕色皮革的真实 PBR 扫描纹理，金属采用细拉丝微表面。三平面采样使用世界位置与世界法线，不依赖合并前后的对象坐标；源和网页代理的纹理方向保持一致。

`public/models/works-gallery-v5-compressed.glb` 保留 77 个资产 ID、原层级、坐标、UV 和 542,976 个三角形。实际完成 8 张 64 samples 昼夜烘焙（三张 4K 与一张 1K，各两套）、2 张反射探针，并采用 KTX2 压缩。运行时切换材质版本，不改变独立交互。

- [近景](../renders/works-gallery-v5/materials-closeup.png)
- [原始几何与 UV 字节比对](../assets/blender/works-gallery-v5/pipeline-verification.json)
- [世界坐标采样审计](../assets/blender/works-gallery-v5/world-triplanar-audit.json)

## 关于我昼夜

关于我使用真实 Blender 夜景烘焙：主体四张、建筑一张，均为 4096×4096、64 samples。奖项和桌面暖灯、建筑、玻璃金属与湖景按同一进度变化；保留原日景文件和源模型。日出和日落各约 15 秒，进入、返回时不另起时钟。

- [完整接入记录](validation/about-web-integration-v3.json)
- [昼夜状态与资源释放检查](../output/about-daynight-lifecycle-audit.json)
- [详细说明](ABOUT_ATELIER_V3.md)

未修改旧项目，未部署，未上传仓库。个人奖项、技能和联系方式仍为“待补充”。
