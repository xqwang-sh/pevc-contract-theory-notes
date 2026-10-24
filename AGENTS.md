# PE/VC 合同理论网页讲义

- 本目录是独立 Git 仓库；网页源文件为 `w04-fund-contract.qmd`、`w05-venture-contract.qmd`，首页单独维护于 `docs/index.html`。
- 在本目录运行 `python3 checks/render_materials.py --sync-parent` 生成两周 HTML 并同步现有课程副本；该脚本在临时目录渲染，避开 OneDrive 临时目录清理权限问题。只改生成文件会被下一次构建覆盖。
- 读者学过高微、高宏与基础计量但未系统学过合同理论；按理解推进，学生材料不写预计用时。材料分为完整学生讲义、每周预习、每周课堂与独立课后习题；当前范围与材料分工以 `教学安排-预习课堂复习.md` 为准。
- 理论模型必须先说明时序、行动、信息、收入与福利口径。区分教学简化、原论文结果和真实合同安排。
- 上层课程目录的 `html-src/` 和 `docs/` 为现有副本；修改交付时保持对应 QMD 与 HTML 同步。完整学生 Markdown 可根据用户要求重写；旧版存于上层 `revisions/`，根目录现行 Markdown 与本仓库 `student-notes.md` 保持一致。
- 本地修改与公开发布分开记录；没有实际推送或部署时，不得声称线上已更新。

- 第 5 周现行主讲是 Hellmann 投入保护、Casamatta 融资与建议捆绑、Cornelli–Yosha 粉饰与转换。每篇先写信息与可契约范围，课堂只推一个核心比较；连续努力、贝叶斯更新和完整定价放附录 G。Aghion–Bolton 仅作预习桥接，Neher、AP 和实验设计为选读。
- Hellmann 二元教学例子固定经营行为，必须明示不足额离职补偿；不能据此证明原文内生补偿或 VC 控制唯一最优。Casamatta 允许创业者自筹资金，融资与建议的价值不依赖缺钱。Cornelli–Yosha 的粉饰发生于获知质量之前，转换必须先于最终现金实现，并检查 VC 中期最优选择。
- 核查算例须从现金分布、行动和合同重新计算 IC、PC 与总剩余，不只断言印出的数字；原文版本与核读位置写入 checks/week5-model-audit.md。
