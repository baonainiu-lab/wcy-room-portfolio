# 终端机首页 V2

2026-09-26，根据用户“终端机模型继续优化、设计背景、画面占比大、带点动效”的要求，直接接入本地首页。人物继续停用。

## 模型与背景

- Blender MCP 在独立 `welcome-terminal-v1.blend` 基础上制作 V2，保存至 `assets/blender/welcome-terminal-v2.blend`，网页加载 `public/models/welcome-terminal-v2.glb`。
- 加入分节铰链、散热凹槽、旋钮滚花和刻度、螺钉与边框细节，优化金属和屏幕材质。保留原屏幕图像、四个 seed 根节点、原始变换及 `TerminalUnfold` 动画。导出清理了布尔和倒角产生的退化面。
- 背景由内置 image_gen 生成，项目副本为 `public/media/terminal-showcase-v1/daylight-atelier.png`。原图来自 `/Users/a90/.codex/generated_images/01a0c3dd-f4f8-7ec0-8cb2-47cf0726ce5e/exec-8ad96f37-550c-4dff-8a58-3e18fd98b0d5.png`；完整提示词保存在 `assets/terminal-showcase-v1/background-prompt.txt`。这是原创生成的背景板，并非可旋转的建筑模型。
- 采用深蓝金属门框、米白矿物表面、日光和少量暖橙灯缝。没有新增第三方图片、角色或字体；现有源码许可证保留。

## 网页行为

- 桌面终端基准展示宽度从视锥宽度的 26% 调到 45%，约放大 73%，并设置高度上限。手机单独控制宽度和位置，保留边缘安全空间。
- 每帧使用实际时间增量驱动缓慢悬浮、低幅转向和阻尼指针倾斜。减少动态效果时停止待机运动。
- 背景在原 WebGL 地面/天空 shader 内显示，不盖住真实模型。下滑时展台背景先柔和退为米白，再沿原环境渐变曲线呈现房间外景，避免双层建筑重影；终端仍是同一个物件，沿连续路径落回原桌面。
- 指针运动在入场开始后冻结相位并平滑退场；完成或跳过时释放监听、恢复原环境 shader，并释放背景纹理。
- 背景加载失败自动回退米白背景。终端/房间加载失败沿用现有错误提示和重试。

## 验证

- 真实 V2 GLB 独立检查 5/5：27 网格、7 材质、26,868 三角面；无退化三角面；61 次动画采样和 49 点桌面支撑检查通过。报告 `docs/validation/welcome-terminal-v2.json`。
- 开场输入及真实房间结构检查 16/16，常驻终端检查 5/5。
- 实际 V2 完整落桌路径检查 10/10：桌面与手机尺寸、静止与 8 秒待机/鼠标偏转两种初态，各采样 549 帧；桌面穿透 0 帧，最小间隙 0.002996。跳过、重复输入、窗口变化、减少动态及最终还原均通过，报告 `docs/validation/terminal-dock-v2.json`。CPU 采样频率不是浏览器实测 FPS。
- 最终生产构建通过；保留原有的大包体积提示，无构建错误。
- 浏览器完成桌面下滑，记录进入一次、完成一次、终端准确落桌、控制恢复、错误为空。手机 390×844 已检查完整构图和指针上滑入口；真实手机硬件触摸未测。
- 截图：`renders/terminal-showcase-v2-desktop.png`、`renders/terminal-showcase-v2-mobile.png`。额外浏览器状态记录见 `docs/validation/terminal-showcase-v2-browser.json`。

仅本地预览：http://127.0.0.1:5173/ 。没有推送仓库或部署。
