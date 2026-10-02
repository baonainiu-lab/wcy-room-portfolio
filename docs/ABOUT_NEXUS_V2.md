# About Nexus V2

本轮重新设计并制作独立的无墙圆形工作岛。当前用于**造型和材质渲染验收**；用户通过前不接入网站。尚未导出网页 GLB，也未完成运行时贴图烘焙、模型与材质优化或性能验证。

可编辑源文件：[about-nexus-v2.blend](../assets/blender/about-nexus-v2.blend)。建模及渲染脚本位于 [about_nexus_v2](../assets/blender/scripts/about_nexus_v2/)。

场景以深蓝金属、暖木、橙色与黄铜细节形成开放的机械工作站，包含：

- **圆形岛台与 C 形木台**：完整底盘、实体支柱与向前开放的工作区域。
- **中央机械档案盘**：由支柱、斜撑和转轴承托的大圆盘，承载个人简介占位内容。
- **三角簇玻璃奖项舱**：三座不同高度的玻璃舱共用底座，内部为独立的抽象展示雕塑。
- **径向技能转盘**：共用木质工作台和中轴，布置可拆几何组件、材质样片扇册及带遮光叶片的光学工具。
- **台面联系终端与返回踏板**：保留实体支撑、独立根节点和操作面，供后续绑定交互。

个人简介、奖项、技能和联系方式均待补充。抽象奖项和工具只是展示容器与视觉隐喻，不代表真实获奖经历、职业技能或熟练程度；没有编造联系方式、社交账号、二维码或评分。

最终验收渲染输出位置如下，均由 Blender 场景渲染生成：

| 视图 | 文件 |
| --- | --- |
| 白天全景 | [day.png](../renders/about-nexus-v2/day.png) |
| 夜间全景 | [night.png](../renders/about-nexus-v2/night.png) |
| 奖项舱细节 | [awards.png](../renders/about-nexus-v2/awards.png) |
| 工作站细节 | [workstation.png](../renders/about-nexus-v2/workstation.png) |

几何和程序材质为本轮在 Blender 中原创制作。场景采用项目现有的原版 **DouyinSans Bold**，字体数据打包于 `.blend`；OFL 许可及来源说明保留在 `FONT_LICENSE_OFL.txt` 与 `ABOUT_NEXUS_README.txt` 文本块中。

验收通过后，再制作网页资产、绑定场景入口与返回操作、设计切镜，并进行近距离结构检查及本地运行性能验证。本轮状态不表示网站已接入，也不包含部署。
