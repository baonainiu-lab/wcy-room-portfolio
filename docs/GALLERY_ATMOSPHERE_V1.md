# 长廊外部光影与真实天空

用户要求在保留精简长廊的基础上，给外部背景增加光影质感，并有符合真实光照的天空。本轮保留 V3 的 77 个资产和六个展位，只修改长廊环境；房间场景环境与旧项目不变。

## 地面与天空制作

地面使用独立 Blender 工程 `assets/blender/gallery-atmosphere-v1.blend`。在真实 V3 长廊下方 Y=-0.88 放置 64×64 的烘焙平面，用细石材材质、原太阳、原馆内灯具以及少量环境补光，真实烘焙日夜 2048² 光照。阴影与底座位置对应，夜间仅在长廊附近保留暖色溢光。Cycles Metal 64 samples，日间 32.99 秒，夜间 38.53 秒；生产模型和原 V3 源未修改。

天空来自独立 `assets/blender/gallery-atmosphere-sky-v1.blend` 的空环境全景渲染。白天采用 Blender 多重散射物理天空与低对比薄云，太阳 Web 方向为 `[0.575766,0.628109,-0.523424]`，与长廊投影方向一致。日间最终采用 1200 米海拔、air density 1.0、aerosol density 0.08，降低低空发灰；原版保存在 `assets/experiments/gallery-atmosphere-v1/sky-before-clear-air/`。用四方位标记和太阳核心像素验证，测得方向误差 0.02484°。夜晚使用深蓝低照度天空与极淡云层，无月亮或星河装饰。两张为 2048×1024，Cycles Metal 32 samples。

输出目录 `public/textures/gallery-atmosphere-v1/`，包含四张 PNG 与四张 KTX2：`day`、`night`、`day-sky`、`night-sky`。UASTC quality 2、Zstd 9、sRGB，保留完整 mip 链。原始光照、颜色管理、UV 方位和哈希见 `SOURCE.json`、`COMPRESSION.json`、`SKY_SOURCE.json`。没有新增外部图片或第三方模型。

## 网页显示

`src/gallery-floor-finish.js` 将地面光照接入已有连续地面 shader，补充轻微随观察角度变化的柔和反光。纹理按世界米制坐标采样，23→32 米渐隐；远处地面向天空雾色融合。物理天空下半球是黑色空域，因此网页在视线低于地平线时使用地平线上方的雾色，并向下层大气颜色渐变，避免白天地面出现黑洞。

天空根据真实世界观察方向采样，KTX2 方位为 `u=.5+atan(d.x,-d.z)/(2π)`、`v=acos(d.y)/π`，横向重复、纵向夹紧，不是固定在屏幕上的背景图。长廊白天界面顶部遮罩由原约 95% 米白减为约 32%，保留文字可读性并透出天空颜色；原房间界面不变。俯视时以地面和远雾为主，降低观察角度可见更多天空。地面纹理采样为 `(worldXZ/64)+.5`，与 KTX2 top-down/flipY=false 匹配。

切镜共同舞台继续保留单地面和单天空，仅创建自有材质，纹理与主题参数按引用共享。地面阴影按长廊世界偏移固定，天空在切镜中段连续混合；回程从长廊天空开始。未新增绘制调用或实时反射渲染 pass。环境拥有四张纹理，舞台材质销毁不释放它们。

## 验证

转场与真实环境 provider 的资源、参数隔离、回程首帧、失败重试、减少动态模式、缩放尺寸等检查通过；最新数量与源码 SHA 见 `docs/validation/gallery-transition-v3.json`。网页视觉、错误和短时性能检查单独记录于 `renders/gallery-atmosphere-v1/web-verification.json`。短时 RAF 统计不代表稳定呈现 120 FPS，用户最终视觉反馈待完成。

仅在本地预览，未上传或部署。
