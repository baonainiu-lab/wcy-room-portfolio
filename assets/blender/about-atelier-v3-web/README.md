# About Atelier V3 · 网页派生资产

此目录记录用户授权的本地网站预览资产，不表示已部署。可编辑源为 `assets/blender/about-atelier-v3.blend`；导出流程从不保存或覆盖该源文件，也不访问已有交互 Blender 窗口。所有 Blender 操作使用独立 `--background` 进程。

## 再现

在项目根目录运行：

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python assets/blender/scripts/about_atelier_v3/web_export.py -- --stage all
/Applications/Blender.app/Contents/MacOS/Blender --background --python assets/blender/scripts/about_atelier_v3/verify_web_export.py
python3 scripts/compress-about-atelier-v3.py --threads 2
```

可单独运行 `--stage prepare`、`--stage bake --indices 0 1 2 3`、`--stage export`。派生准备文件为 `assets/blender/about-atelier-v3-web.blend`。重新 prepare 会产生新的 preparation_id，旧图集不能混用。导出通过后才原子替换最终 GLB。

## 几何与层级

仅导出源中 `01_ATELIER_Platform`、`02_ATELIER_Archive`、`03_ATELIER_Workbench`、`04_ATELIER_Furniture`。`90_RENDER_Atrium_Lake` 与离线灯光仅参与烘焙；不包含在网页 GLB 中。

原有 128 个 `asset_id` 根、原枢轴、ID 父子关系及 `interaction` / `interactive` / `content_status` 均保留。片段仅在同一资产内部按材质类型合并。原本没有资产根的四块地台部件放入匿名 `ATELIER_STATIC_PLATFORM`，不新增伪造的资产 ID。曲线截面和 bevel 圆角分段降低到 2，其余几何不做 decimate。实际三角形、网格数、ID、坐标与验证结果以 JSON 报告为准。

## 烘焙与程序材质

四张 4096 × 4096 日光图集分别对应四个源集合；Cycles COMBINED，32 samples，16 px 边距，AgX 色彩变换沿用源场景。图集已经包含日光、阴影与间接光，运行时使用 unlit，并令 `toneMapped=false`。

在合并之前，将每片源对象的局部坐标和 split normals 分别保存为 `AtelierSourcePosition` / `AtelierSourceNormal` 网格属性。材质 Object 输入和物体空间法线输入改为这些属性。胡桃木现有显式三 FLAT 投影和四次方法线权重网络保留；其他原 BOX 采样转成显式源局部三平面采样。这样合并、UV 展开与 bake proxy 不会让胡桃木纹方向随合并对象改变。

玻璃和黄铜/拉丝钢保留独立实时 PBR 材质；极细程序金属粗糙度采用源中心值 0.24，保留 metallic=1。玻璃保持透射 1、IOR 1.46、roughness 0.055。真实湖景 HDRI 用于运行时 PMREM 环境反射；无远山模型，也没有把概念图用作场景贴片。

只有日光烘焙。运行时降低 unlit 颜色可做明暗过渡，但不等同于重新计算夜晚阴影或离线夜景烘焙。

## 运行时接口

| 内容 | 接口 |
| --- | --- |
| 优先模型 | `/models/about-atelier-v3-compressed.glb` |
| PNG 兼容模型 | `/models/about-atelier-v3.glb` |
| 图集材质 | `ATELIER_LIGHTMAP_0` … `ATELIER_LIGHTMAP_3` |
| 图集路径 | `/textures/about-atelier-v3/day-0` … `day-3`，`.ktx2` / `.png` |
| 玻璃材质 | `ATELIER_GLASS` |
| 金属材质 | `ATELIER_METAL_SatinBrass`、`ATELIER_METAL_BrushedSteel` |
| 环境反射 | `/textures/about-atelier-v3/landscape/lake_pier_2k.hdr` |
| ID 与交互 | `node.extras.asset_id` / `interactive` / `interaction` |
| 坐标 | glTF Y-up，米制；源 `(x,y,z)` → glTF `(x,z,-y)` |

压缩 GLB 内嵌 KTX2，兼容 GLB 内嵌 PNG。外部图集文件仅作为可检查副本/显式替换资源；正常 GLTFLoader 可直接复用已经加载的内嵌图集，避免再次下载/占用纹理内存。

## 验证与来源

- `preparation-report.json`：源哈希、源 ID 层级、优化后的几何与 UV 图集。
- `export-report.json`：最终 GLB、材料接口、边界、图集哈希。
- `validation-report.json`：原始 128 根世界矩阵与 glTF 递归世界矩阵逐项比较、完整顶点有限性与边界、互动字段、图集内嵌数据哈希。
- `compression-report.json`：官方 KTX 工具验证、mipmap 链、128 ID 与源 audit 匹配、所有非图集 bufferView 和其他 JSON 的保留检查。

几何由本项目原创；贴图/HDRI 使用已核实 CC0 来源，见 `assets/textures/about-atelier-v3/README.md`、`texture-manifest.json`、`landscape/manifest.json`。源字形为未修改 DouyinSans Bold，OFL 文件保留于 `assets/font-candidates/v4/douyin-upstream/DouyinSans/OFL.txt`。用户奖项、履历、技能、联系方式仍为占位，不代表真实个人成绩。
