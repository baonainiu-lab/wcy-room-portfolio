# 轨道创作舱 · Blender 制作工程

本目录是经用户授权后，通过 Blender MCP 实际创建的模型源工程；不是 AI 生成概念图。概念参考在 `../../docs/concepts/v2/`。

## 当前交付 · V14

当前可编辑源为 `orbital-atelier-v14.blend`，网页 UV 与烘焙工程为 `orbital-dual-bake-v14.blend`，本地已接入 `../../public/models/orbital-atelier-v14.glb`。本轮优化建筑与平台金属边沿的连续 UV 和纹素密度，保留 V12 几何、V13 灯光与所有独立交互资产。完整参数与边界见 [V14 记录](../../docs/MODEL_EDGES_V14.md)、[交付元数据](edge-precision-v14-delivery.json)。

用户已授权先替换到本地网站验看；最终渲染仍待视觉验收，不推送或部署。

## V2 初始制作历史

- 主工程：`orbital-atelier-v2.blend`。
- 主场景：`ORBITAL_ATELIER_V2`。
- 独立素材场景：`ENV_CITY` / 后续修订场景，以及 `SCREEN_ART`。
- 材质纹理与环境渲染：`../textures/`；所有实际使用的图像已打包到 .blend。
- 真实渲染图：`../../renders/`。
- **以下为初始 V2 制作状态，后续本地接入以顶部 V14 记录为准。**

用户要求完整还原参考图，并在首轮试渲染后指出比例、资产密度的差距。当前修订纠正工作台朝向，重做软包曲面，提升小资产细节，并按用户最新指令在玻璃窗下方增加五组陈列物。当前场景仍需由用户判断还原程度，不能把脚本执行成功等同于视觉验收通过。

## 通过 MCP 执行的模块

| 模块 | 职责 |
| --- | --- |
| `scripts/common.py` | 共享材质、Blender 生成的微表面纹理与基础几何函数 |
| `scripts/build_room.py` | 房间、地台、框架、窗、屏幕、主机、摄影机与灯光 |
| `scripts/furniture.py` | 独立家具根节点：工作台、座椅、软包休闲椅、茶几、地毯 |
| `scripts/props.py` | 六件核心资产与桌面物件、生态球、植物；保留独立关节、卡匣、花瓣、键帽等 |
| `scripts/environment.py` | 原创三维城市、云海、行星的独立环境场景 |
| `scripts/screen_art.py` | 原创橙铜/冰蓝花瓣雕塑的独立三维屏幕作品场景 |
| `scripts/refine_scene.py` | 对照试渲染调整工作台方向、家具比例、材质与摄影机 |
| `scripts/refine_architecture.py` | 连续金属结构带与窄缝照明 |
| `scripts/density_assets.py` | 窗下五组可见独立物件，以及右侧花器植物 |
| `scripts/finish_scene.py` | 窗下连续展台、屏幕渲染贴图、透明主机结构与织物表现 |

复建流程：在新的 Blender 工程中先执行 `build_room.build()`；分别创建并渲染环境和屏幕场景至 `assets/textures/window-city-v2.png` 与 `screen-art-render.png`；回到主场景依次执行 `refine_scene.apply()`、`refine_architecture.apply()`、`finish_scene.apply()`。模块中路径按当前独立项目设置。

`refine_scene.apply()`只重建本任务生成的 `FURNITURE` 与 `PROPS`；所有模块均避免访问旧网站目录。运行制作脚本前应保留 .blend 的人工编辑副本。

## 初始交互与网站适配计划（历史）

家具、小资产各有独立 Empty 根节点和稳定 `asset_id`；需要运动的子部件保留独立节点。材质可共享，逻辑物件不合并。建模细节层级尚未做网页性能精简；渲染验收后再进行烘焙、网格/贴图优化、glTF 导出与模板交互重绑，不能把未经优化的完整渲染工程直接当作网页发布模型。

## 资产来源

本轮房间、家具、小物、城市、屏幕三维图形及微表面纹理由本任务的 Blender Python 模块原创生成，无外部付费素材或来源不明模型。设计依据为本项目 V2 概念图；这些图形不表示用户已提供真实履历、奖项、项目或社交信息。

模板原版 MIT 许可与第三方素材核查仍保存在项目根目录及 `docs/`；本轮建模不改变其许可记录。
