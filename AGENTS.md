# PE/VC 合同理论网页讲义

- 本目录是独立 Git 仓库；网页源文件为 `w04-fund-contract.qmd`、`w05-venture-contract.qmd`，首页单独维护于 `docs/index.html`。
- 在本目录运行 `python3 checks/render_materials.py --sync-parent` 生成两周 HTML 并同步现有课程副本；该脚本在临时目录渲染，避开 OneDrive 临时目录清理权限问题。只改生成文件会被下一次构建覆盖。
- 读者学过高微、高宏与基础计量但未系统学过合同理论；按理解推进，学生材料不写预计用时。材料分为完整学生讲义、每周预习、每周课堂与独立课后习题；当前范围与材料分工以 `教学安排-预习课堂复习.md` 为准。
- 理论模型必须先说明时序、行动、信息、收入与福利口径。区分教学简化、原论文结果和真实合同安排。
- 上层课程目录的 `html-src/` 和 `docs/` 为现有副本；修改交付时保持对应 QMD 与 HTML 同步。完整学生 Markdown 可根据用户要求重写；旧版存于上层 `revisions/`，根目录现行 Markdown 与本仓库 `student-notes.md` 保持一致。
- 本地修改与公开发布分开记录；没有实际推送或部署时，不得声称线上已更新。

- 第 5 周按三个问题组织：第一部分 Aghion–Bolton 的一般控制权机制，接 Kaplan–Strömberg 的真实合同证据；第二部分 Schmidt（2003）的先后投入与可转换证券；第三部分 Neher（1999）的分阶段承诺。Hellmann 完整移入附录 G.1，Casamatta 完整保留于附录 G.2；两者不再承担正文主讲。
- 主讲模型必需的行动、IC、PC、重谈和福利推导均在正文。Neher 原文 Example 4.1 的两期逆推不再只放附录；必须说明确定收益、信息对称、人力资本不可强制转让、资产积累、VC 对整条路径的承诺和延迟成本。0.6／0.4 是可行路径，不是最优路径；最优路径条件留附录 F。
- Kaplan–Strömberg（2003）期刊版为 14 家 VC、213 笔投资、119 家企业。Gompers（1995）是代理与监督预测的实证论文，不能当作 Neher 承诺机制的单独因果检验。后续阅读地图分别说明 Bergemann–Hege、Admati–Pfleiderer、Cornelli–Yosha、Repullo–Suárez 的新问题；粉饰与转换教学例子在附录 G.3。
- Hellmann 二元例子固定经营行为、给定不足额离职补偿，不能单独证明原文内生补偿或控制唯一最优。Casamatta 允许创业者自筹，融资与建议的价值不依赖缺钱。Cornelli–Yosha 的粉饰早于获知质量，转换早于最终现金实现，必须检查 VC 的中期最优选择。
- Aghion–Bolton 的 y 是条件期望货币收入，lambda 是创业者私人收益；完美可核实信号是合同完备基准，正文使用有噪声信号并允许受财富约束的重谈。核查从原始合同与分布重新求行为、收入和福利，原文版本与位置写入 checks/week5-model-audit.md。
- 预习 P5-1 至 P5-4 对应分配、控制、Schmidt 投入与转换、分期承诺。核心题 H5-1 至 H5-5 对应分配、一般控制权、Schmidt 的 VC 响应、Schmidt 的创业者偏离与重谈、Neher；H5-6 至 H5-13 为后续选做，H5-12／13 分别保留 Hellmann／Casamatta。学生材料不标预计用时，教师的节奏安排见教学安排文件。

- Schmidt 正文依据正式版第 II 节 Proposition 3，K=0；创业者先投入，VC 观察后行动，转换权在 VC 完成行动后仍有效。数值为教学构造：I=1，C=5/4，alpha=1/3，概率1/4、1/2、1/4；创业者努力0、1、2。必须检查六种 VC 行动／转换组合、转股却不支持、少投入后的重谈、多投入、资本 PC 与福利。e=2 处是弱实施，按无差异时有效支持；不能宣称严格或唯一。checks/schmidt_model.py 从原始现金表精确分段复算，保留 Casamatta 与 Hellmann 的既有检查用于附录。
