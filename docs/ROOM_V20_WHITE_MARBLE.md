# Room V20 — 白色大理石墙面与黑色纹理顶部

状态（2026-10-01）：`locally_integrated_browser_checked`。本地默认版本已切换为 **Room20 / Gallery5 / Terminal3**，生产构建和完整 CPU 资产验收通过。实际网页的日夜、近景、旋转及场景往返已通过本轮检查；等待用户对最终外观验收。未部署。

用户要求：“房间场景墙壁换成白色大理石材质吧 纹理感突出”；后续要求：“顶部做成黑色的 也要有纹理”。

## 制作范围

房间背墙与侧墙使用白色石底和自然走向的灰色矿脉，上方墙体收边使用黑底浅纹石材。白墙使用 ambientCG Marble005，黑顶使用 Marble002，均为完整 4K PBR 贴图；世界坐标三平面投影的尺度分别为 5.6 米和 5.2 米。保留 V19 的深色木地板、顶部暖光灯、家具、小资产、原始模型几何、UV 和交互标识。长廊维持 V5 原始 sRGB 光照；终端维持 V3；关于我维持已批准的 38 项资产。

墙体和部分设备原来共用材质：仅对房间静态墙体的材质槽建立局部副本，并通过墙面区域遮罩切换表面。Prepared 场景改变 3 处绑定；editable 场景保留历史房间变体，改变 20 处绑定、建立 8 个材质副本。全文件其他对象的实际材质槽、旧材质节点图、灯光参数和几何均保持。法线与高度图只提供表面微细节，没有几何位移。

第一至三轮原生程序石纹未发布，保留于 review history。第四轮使用的官方 CC0 许可、素材包和包内文件哈希保存在 `assets/textures/room-marble-v20/`；8 张实际使用的图像已打包进 Blender 源文件，打包字节与官方原始 PNG 一致。Color 使用 sRGB，Roughness、NormalGL 和 Displacement 使用 Non-Color。ambientCG 将这些来源素材标注为 `PBRProcedural`，不冒称扫描。

## 光照与网页集成

白色墙面改变间接反射，因此 13 组日夜光照和 3 张开场图全部以 96 samples 重新烘焙，2 张反射探针以 64 samples、2048×1024 重新计算。A0/A8 表面数据以 8 samples 新烘焙；其余 11 个槽在材质图、几何、UV 和法线证明一致后继承。对应 22 张 normal/specular KTX 与 V19 原字节一致。最终运行时资源共 58 张 KTX；29 张光照图全部绑定同一最终 V20 prepared SHA。

本次源场景制作、表面与日夜/开场烘焙、反射探针和原始 GLB 导出均通过文件模式 Blender MCP 和 Python 辅助脚本完成，没有离线 CLI 烘焙或接收面分区。最长单张光照烘焙为 101.75 秒。前台交互 MCP 端口未连接；文件模式操作没有打开、切换或保存用户前台场景。压缩和资产验收使用 CPU。详见[制作方式记录](../assets/blender/room-v20-execution-method.json)及[交付清单](../assets/blender/room-v20-bake-delivery.json)。

`src/material-release.js` 已将默认整体版本设为 `room20-gallery5-terminal3`：房间资源使用 `/textures/lighting-v20`、开场资源使用 `/textures/intro-clean-v20`。显式 `?physicalPreview=0` 的旧版入口保持。

## 最终资源

| 资源 | SHA256 |
| --- | --- |
| `assets/blender/orbital-atelier-v20.blend` | `20c1e8f7582fb4532264b6f93e48aad6ca26d69e89157b5c098aa3d3005e60e0` |
| `assets/blender/orbital-dual-bake-v20.blend` | `88fc6d9c51dc70909c6c7e5154d8d755a60f30dd8f75174108a360ccf487f33a` |
| `public/models/orbital-atelier-v20.glb` | `e110ba6c95c10d646713a9b298dcbf5b31d8759ae4a3af9798647e19146a0689` |
| `public/models/orbital-atelier-v20-compressed.glb` | `f2779105330bbd9f65d3c88a095e81d8aa1e5315bd1464d6351b9d7156392621` |

压缩模型为 59,389,600 bytes。源文件和压缩模型保持 V19 的 418,383 个三角形、199 个节点、103 个绘制图元、96 个独立资产 ID；几何、UV、法线、索引、层级、变换和归属逐项一致。

## 验证记录

[完整 CPU 验收](../assets/blender/photoreal-materials-v20-validation.json)为 `cpu_release_passed`。全部 58 张 KTX 的哈希、线性色彩空间和完整 mip 链通过；夜间超范围辐亮度 sidecar 恢复通过；434 项冻结文件保持，其中包括已批准的 About 38 项资产。[几何审计](../assets/blender/room-v20-geometry-audit.json)和[制作记录一致性核验](../assets/blender/room-v20-provenance-validation.json)分别保留证据。

实际 Cycles 第四轮[日景](../renders/room-materials-v20/day-review-4.png)与[夜景](../renders/room-materials-v20/night-review-4.png)已保存。生产构建通过。[实际网页记录](validation/room-v20-main-browser.json)覆盖加载完成后终端欢迎页、箭头进入、昼夜与中间混合状态、缩放旋转、显示器进入长廊及返回、书本进入关于我及返回。两次首次切换观测资源请求维持 78；控制台警告与错误为空。正面强反光视角的黑石会显浅，正常俯视构图保持深色基底和浅色纹理。此记录不代表用户最终视觉验收，也不宣称稳定 120 FPS。
