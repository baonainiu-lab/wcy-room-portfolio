# 个人房间作品集 · 本地试预览

「轨道创作舱」当前为 **V14 模型 + UI V7 实时旋转首页 + V6 房间机械运动**。用户从三张首页概念中选择了 B「日光画册」，现已实现米白日光纸面、寒蝉圆黑 Heavy 立体大标题、左侧入口和右侧真实三维房间。首页房间以 26 秒周期左右各约 18° 自动旋转，可拖动至左右 35°，内部 12 个部件同步活动。标题错落入场，纸面暖光、细线和按钮反光补充动态。详见[实时首页](docs/HOMEPAGE_ROOM_V7.md)及[首页动效](docs/HOMEPAGE_MOTION_V7.md)。详见[首页 B 实现](docs/HOMEPAGE_B_V2.md)及[三张概念与选择记录](docs/concepts/homepage-v2/README.md)。

房间自动运动扩展为 12 个独立部件：椅子左右各 20° 转动并停留，机械花沿真实铰轴依次开合，另有音箱轻摆、无人机轻浮、时钟、镜头、旋钮、雕塑、灯头和通讯器动作。悬停、点击、面板与拖动保留优先权，减少动态效果偏好可关闭自动运动。详见[房间运动 V6](docs/MOTION_V6.md)。

[打开本地预览](http://127.0.0.1:5173/)。首页进入后衔接白天场景，保留整间房生长和双幕揭开；首页与房间共用一个渲染器和模型资源，按阶段绘制；进入时恢复全屏画布及房间交互。构建（23 模块）、7 项实时首页、12 项 motion 与 4 项 entry 检查通过，本轮首页 844 / 390 / 320 px 核验通过。角色暂不接入，个人资料待补充，未部署；稳定 120 FPS 尚未得到验证。

V14 窗框、墙顶、展示柜框和平台侧沿的连续 UV / 局部烘焙保留，重点纹素密度为 V13 的约 1.95–2.33 倍；三角形数不变。详见[模型边线 V14](docs/MODEL_EDGES_V14.md)。

独立目录：`/Users/a90/Documents/ChatGPT/个人网站/room-portfolio`。项目直接基于 [Sooah 模板](https://github.com/andrewwoan/sooahs-room-folio)，`../sooahs-room-template` 为上游参考；不迁移、不修改旧网站 `/Users/a90/Documents/wcy90-portfolio`。

## 本地运行

安装 Node.js 与 pnpm 后，在本目录运行：

```sh
pnpm install --frozen-lockfile
pnpm dev
```

以终端输出地址为准，服务器仅绑定 `127.0.0.1`；`pnpm build` 构建，`pnpm preview` 本地预览构建结果。依赖版本由 `pnpm-lock.yaml` 固定。

## 当前房间 · V14

- 完整源为 `assets/blender/orbital-atelier-v14.blend`，网页 UV 工程为 `assets/blender/orbital-dual-bake-v14.blend`；网页模型 `public/models/orbital-atelier-v14.glb` 为 49,383,384 字节、373,203 三角形、102 绘制图元。37 个室内根资产、93 个室内 ID 和 2 个外景 ID 保留。
- 左墙由 0.22 m 加厚至 0.38 m，后墙由 0.27 m 加厚至 0.43 m，均向外增加 0.16 m；上沿升高 0.35 m，金属框同步加深，增加 L 形墙脚承托，室内窗与家具位置保留。
- V11 的窗角避让保留；V12 修复 8 个建筑对象的平滑 / 硬边与倒角，顶带和前立柱严格自穿透检测降为零，顶带最大切线转角由 15.38° 降至 5.57°，窗上净空约 12.377 cm。建筑保留完整评估几何，终端各用 10k、盆景 baked 网格用 18k 预算。详见[精度改进与取舍](docs/MODEL_PRECISION_V12.md)。
- V13 夜间图集 0–7 全部重烘；桌下 32 W、窗下左右 22 / 17 W 的暖光烘焙进现有图集，不新增网页灯光、几何或图集数量。8 张白天图集与日景窗图的哈希均与 V12 相同，夜景窗图亦保留。详见[夜间暖光交付](docs/NIGHT_WARM_V13.md)。
- 夜景背景已压暗；外部泊位、展廊的夜间图集 5 / 6 在线性空间分别乘以 0.28 / 0.12，室内和白天不作这项调整。V13 夜景目视检查已完成，局部暖光与冷暗墙面保留。
- 保留模板的房间浏览、镜头控制、加载进入、物件交互与面板机制。小资产默认 1.8 倍悬停，大件采用较小倍率；UI 已按批准概念实现；原 UI 的视口与交互检查作为历史记录，当前字体 V3 检查以本轮记录为准。
- 姓名、简介、项目、头像、联系方式和物件个人含义仍为“待补充”，场景美术不冒充用户真实作品。角色入口与交互保持撤下，试作保留待定。

## 检查范围

当前 V14 [导出检查](renders/edge-precision-v14-export-check.json)及入场 / 运动逻辑检查通过；本轮精度、成本与边界见 [V14 记录](docs/MODEL_EDGES_V14.md)。以下 V13 记录保留为历史基线。

[V13 资产校验](renders/asset-validation-v13.json)与[连续性检查](renders/night-warm-v13-continuity-check.json)通过：全部导出几何、UV、法线、索引、节点层级与变换和 V12 精确一致，9 张日间图像逐字节一致。[可编辑日景核验](assets/blender/source-day-v13-verification.json)也通过。

以下为 V13 + UI V2 阶段的历史基线：当时 `pnpm build` 通过（20 个模块），夜景目视检查已完成。[本轮性能报告](renders/performance-night-warm-v13.json)记录 844×795、DPR 2 的夜间静置画面 51.12 秒 / 8 次快照：FPS 中位数 120.48，帧间隔 P95 为 9.8–10.2 ms，GPU P95 为 4.268–5.625 ms，`errors: []`；`stable120Verified` 仍为 `false`。详见[预览检查](docs/PREVIEW_CHECK.md)及[调整后网页](renders/night-warm-v13-after-web.png)。

上述 V13 阶段的昼夜切换、显示屏打开作品、Esc 关闭回归已通过；当时字体 844 / 320 px 检查为桌面浏览器视口模拟。UI V1、V2 与 V12 的报告仅作历史基线，不替代当前 UI V3 检查；最终视觉仍待用户验收。

仅本地预览，不上传旧 GitHub 仓库或部署旧域名。新仓库与部署位置待用户确定。

## 制作与来源

- [资产流程](docs/ASSET_PIPELINE.md)与[第三方素材台账](docs/THIRD_PARTY_ASSETS.md)
- [任务范围](docs/SCOPE.md)、[阶段记录](project-status.json)与[Blender 工程说明](assets/blender/README.md)
- [V2 房间概念](docs/concepts/v2/README.md)、[角色方案状态](docs/AVATAR_IMPLEMENTATION_PLAN.md)
- [上游 README 与致谢](docs/UPSTREAM_README.md)、[原版 MIT 许可](LICENSE.md)

Andrew Woan 的 `LICENSE.md` 原样保留；依赖与第三方素材分别记录许可，不把全部资源统称 MIT。
