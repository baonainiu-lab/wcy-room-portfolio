# 首页实时房间 V7

用户要求首页模型会旋转，并增加整体动效。`src/homepage-room.js` 将原静态房间主视觉接为真实 WebGL 房间预览；首页版式及其他界面动效由首页样式实现负责。

## 预览行为

- 共用当前 renderer / canvas / WebGL context；不创建第二个 renderer，也不请求第二份 GLB。
- 从完成光照绑定、尚未执行入场缩放的真实房间克隆 Object3D 层级。93 个室内资产标识保持独立；几何、材质、贴图为同一引用。外景不在首页克隆中。
- 26 秒一周期、左右约 18° 自动转动，轻微上下浮动不超过 12 mm。预览内沿用 12 个房间部件的运动，包括椅子、花瓣、音箱、镜头等。
- 横向拖动可转至左右 35°，释放后平滑回到自动转动。6 px 水平意图阈值；优先竖向移动时释放 pointer capture，保留手机页面滚动。
- 使用正交镜头；启动时计算所有真实顶点在完整允许角度内的投影极值，包含角度区间内部极值。ResizeObserver 与窗口 resize 更新画布及镜头。帧循环不读取布局、不做拾取射线、不重载贴图。
- 首次成功渲染后才添加 `.entry-art.is-live`，由 CSS 隐藏原静态图片。加载/编译失败会恢复原图和画布归属，房间入口可继续使用。
- `prefers-reduced-motion` 下没有自动旋转、浮动或内部自动运动，但保留用户主动拖动。文档不可见时停止预览更新和渲染。

## 生命周期与对接

```js
const homepageRoom = await createHomepageRoom({
  THREE, renderer, room, element: document.querySelector('.entry-art'),
  canvas, reducedMotion,
});
// 在原有统一 requestAnimationFrame 中执行，不开启新循环：
homepageRoom.update(delta);
homepageRoom.render();
// 首页文字和画面淡出后，将同一画布归还房间：
homepageRoom.release();
```

创建必须发生在 `prepareIntro()` 前。主 renderer 须支持 alpha；入口场景透明，保留原纸面背景。`release()` 可重复调用：恢复原 canvas DOM 位置、样式、当前窗口的绘制尺寸与 canvas CSS 宽高、DPR、清屏颜色/透明度及 scissor 状态，断开所有预览监听器。不会 dispose 任何共享材质、几何或贴图。

## 自动验证

运行：`node scripts/check-homepage-room.mjs`

使用当前 `src/main.js` 实际引用的 V14 GLB 与真实 Three.js 数学/对象；仅 DOM 和 GPU 提交用轻量替身，未用假模型代替房间验证。7 组检查通过：

1. 93 个资产标识、12 个运动部件、资源引用共享与变换对象独立。
2. 模拟 32 秒：自动转角实测 −17.967° 至 +17.967°；12 个部件都运动；原房间所有变换保持；帧循环无布局读取。
3. 水平拖动限制、竖向滚动释放、松手回到自动转动。
4. 对每个真实顶点，在 720×500、300×370、1200×280 三种比例、−35° 至 +35° 每 5° 检查画面边界及近远裁剪；最大 NDC 绝对值 0.928，未裁边。
5. 页面隐藏暂停、重复释放、DOM / renderer 还原；首页期间窗口缩放后，归还画布的绘制与 CSS 宽高均跟随当前窗口；已排队的 ResizeObserver 回调无法再次调整 renderer；监听器清理，无共享资源 dispose。
6. 减少动态效果时自动运动完全关闭，手动旋转保留。
7. 编译失败时清理预览并还原静态 fallback / 房间画布。

上述为确定性行为检查；实际 GPU 性能、透明底色、首帧与入场交接需以本地浏览器检查为准。没有新增模型三角面或新增 GPU 几何资源；首页和进入后的房间按阶段共用一个画布，不同时提交两套场景。

## 联合浏览器验收记录

2026-09-22：844×795、390×844、320×568 首页完整构图与真实旋转通过；横向拖动改变三维视角。320 短屏无横向溢出，页脚保留 25 px 纵向滚动。首页期间改变视口再进入，画布 CSS 与绘制尺寸均正确恢复到当前窗口。静音进入、作品面板开关、日夜控制回归通过，浏览器 warning / error 为空。手机尺寸使用桌面视口模拟。

最终构建 23 模块通过，CSS 37.28 kB（gzip 8.56）、JavaScript 1135.66 kB（gzip 350.19）；仅常规大包提示。7 项 homepage、12 项 scene-motion 和 4 项 room-entry 检查通过。详见[浏览器记录](../renders/homepage-live-v7-browser-check.json)与[性能记录](../renders/performance-homepage-live-v7.json)。短时采样不代表稳定 120 FPS。
