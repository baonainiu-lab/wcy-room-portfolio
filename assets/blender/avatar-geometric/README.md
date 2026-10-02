# 小轨 / Orbit

这是为作品集制作的原创几何角色。先完成真实 Blender 模型，再由同一模型生成设定渲染与网页资产；没有使用需要二次猜测形体的 AI 概念图。

形象由暖白陶瓷外壳、石墨色关节、橙色功能部件组成。偏置天线、三瓣创作徽记与绘图终端形成辨识点。身体采用可以清楚解释的机械分段，适合 Codex 通过 Blender Python 重复生成、调整和驱动交互。

## 文件

- `build_avatar.py`：完整参数化建模、材质、导出、渲染脚本。
- `geometric-creator-v1.blend`：保留独立部件的可编辑 Blender 文件，以及独立摄影棚灯光和相机。
- `manifest.json`：尺寸、材质、轴向、动画枢轴和统计信息。
- `../../../public/models/avatar/geometric-creator-v1.glb`：网页使用的优化模型。
- `../../../renders/avatar-geometric/geometric-creator-v1-studio.png`：由同一模型直接渲染的形象预览。

## 重建

在项目根目录执行：

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python assets/blender/avatar-geometric/build_avatar.py
```

脚本在独立后台进程中建立新场景，不读取或覆盖房间文件，也不操作当前打开的 Blender 场景。已在 Blender 5.1.2 中执行验证。

## 几何与交互合同

Blender 坐标：Z 向上，正面朝 −Y；glTF 坐标：Y 向上，正面朝 +Z。身高约 1.789 米，脚底落在零平面。

`GeometricCreator` 根节点包含 `AvatarBody`、`AvatarHead`、`AvatarArmL`、`AvatarArmR`、`AvatarTerminal`。头部可绕 glTF Y 轴转向、绕 X 轴点头。`EyeL` / `EyeR` 是独立的胶囊形网格，以局部 Y 缩放眨眼。`AvatarArmL` 是自由挥手臂；另一只手握住终端。所有物件以刚性关节驱动，不依赖皮肤骨架或复杂变形。

材质共七种，不含外部纹理、字体或第三方模型。网页导出时，仅在相同刚性父节点与相同材质内部合并静态网格，保留头部、手臂、眼睛、终端边界。Blender 文件继续保留所有原始独立零件。

`asset_id = avatar.creator` 标记整个人物，`asset_id = avatar.terminal` 标记作品入口。`WarmLED` 为眼睛与微笑发光材质，`ScreenMint` 为终端线稿。

## “一致”的准确范围

形象图和网站使用同一套几何、比例、结构及材质数据，因此不存在根据图片重新建模时的人物变形或相似度偏差。摄影棚与网页的灯光、相机、色调映射、浏览器和屏幕会影响最终像素，不能把同一模型理解为所有环境下的截图逐像素一致。

源文件用于后续换色、修改比例与更新交互；改动设计后应重新运行脚本，同步更新设定渲染和 GLB。
