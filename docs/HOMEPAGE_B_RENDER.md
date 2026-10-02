# 首页 B · 真实房间渲染

用户选择「B 日光画册：明亮米白＋大标题」后，为首页单独制作透明房间主视觉。使用实际 V14 GLB 与网站同一套日间烘焙贴图，不直接使用概念图中的房间替代现有模型。

- 文件：`public/textures/home/room-day-v14.png`
- 尺寸：1800 × 1250；8-bit RGBA；1,902,032 bytes
- Alpha 范围：0–1；非透明边界 `[94, 55, 1706, 1195]`（右/下边界不包含）
- 透明余量：左/右各 94 px，上/下各 55 px；边缘未裁切
- 完整保留室内 37 个根节点、93 个资产 ID 与矩形圆角平台
- 仅在临时渲染场景隐藏 `environment.orbital_dock` 与 `environment.warm_gallery`，方便放置在米白首页背景上
- 采用原房间的三分之四正交视角；Cycles 32 samples、透明胶片、Standard 色彩变换；没有后期修改像素

原始 `.blend` 未保存或修改。网页 GLB 渲染前后的 SHA-256 相同：`a933ce1ba865c5ad5293e11bfac51ad082f8c1522ff828ad89d45aa17bd5e232`。

图像 SHA-256：`68bb59e4fb1008b1894893581c9f920bcbd579905b8064c3fb3c509e1c059a81`。

可复现脚本：`assets/blender/scripts/render_homepage_b_v14.py`。渲染与 alpha 检查记录：`renders/homepage-b-room-render.json`。该 PNG 是静态首页插图，不替代可交互的房间，也不作为帧率证据。玻璃在 Blender 与网页自定义着色器中可能有轻微差异。
