# 终端机 V2：Blender 精度与材质

本轮只优化既有终端机。模型在独立 Blender 文件中完成，原 V1 模型和房间文件未改写；没有接入人物或第三方模型、贴图。

- 源文件：`assets/blender/welcome-terminal-v2.blend`
- Blender 操作记录：`assets/blender/build-welcome-terminal-v2.py`
- 网页模型：`public/models/welcome-terminal-v2.glb`
- 来源与校验：`public/models/welcome-terminal-v2.source.json`
- 新渲染：`renders/welcome-terminal-v2-blender.png`
- 原渲染：`renders/welcome-terminal-v1-blender.png`

外壳保留原蓝色、钛银与橙色，细化涂层反光，加入实际凹入的散热槽、端口、螺钉、分段铰链、细金属屏框、扬声孔、传感器、旋钮滚花和刻度。装饰零件按原交互根节点和材质合批，共 27 个网格、7 个材质、26,868 个三角面，GLB 约 4.8 MB。

屏幕保留项目原有 2880 × 1200 图片，嵌入 PNG 与源文件字节一致。屏幕使用单层防反光 PBR 表面，避免叠加透明玻璃造成排序或共面闪烁。渲染审查后降低镜面和涂层反射，保留原橙蓝图案的可读性。

`seed.base`、`seed.lid`、`seed.dial`、`seed.rail` 的原始变换和 `TerminalUnfold` 四条轨道保持不变。Blender 在 1、25、49、73、97 帧对比，根节点矩阵误差与包围盒扩张均为零，维持原有桌面放置和开场接口。

首次导出检查发现微小倒角及布尔切槽留下退化三角形。已在 Blender 合并重合顶点、明确三角化并重建加权法线，细节倒角降为两段；保持独立验证标准。最终通过几何、UV、单位法线、四根节点、61 个动画样本、独立交互及桌面支撑检查，实测桌面净空 0.003。校验报告为 `docs/validation/welcome-terminal-v2.json`。这些检查不等同于帧率保证；网页构图、镜头衔接和响应式由主任务另行实测。
