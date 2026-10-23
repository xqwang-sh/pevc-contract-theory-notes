# PE/VC 合同理论教学材料

面向学过高微、高宏与基础计量、尚未系统学习合同理论的金融博士生。第 4 周研究 LPA 合同，第 5 周研究 GP 与企业合同，以 VC 为主。

- 完整学生讲义：student-notes.md，由 student-notes.qmd 生成 HTML，正文连贯解释，拓展进入附录。
- 短预习：w04-preparation.qmd、w05-preparation.qmd，包含基础概念、公式与自查答案。
- 课堂讲义：w04-fund-contract.qmd、w05-venture-contract.qmd，每讲有动机、内容安排、模型衔接、必要推导与计算。
- 课后习题：exercises.qmd，核心题与附录选做分开，提供折叠分步答案。
- [教学安排与模型口径](教学安排-预习课堂复习.md)记录材料对应、模型参数与文献来源。

在本目录运行 python3 checks/render_materials.py 生成六个 HTML 页面；它在本地临时目录渲染，避免 OneDrive 临时目录清理权限错误。需要更新课程目录副本时加 --sync-parent。首页 docs/index.html 独立维护。全部页面自包含，沿用 pevc-handout.css。源文件和 HTML 的课程目录副本按 AGENTS.md 同步。

2026-10-22 按“权利地图 → Aghion–Bolton 控制配置 → Admati–Pfleiderer 知情续投 → Bolton、Liu、Nanda、Sundaresan（2024）信息生产”重排第 5 周；Neher 保留为分阶段承诺的对照分支。Kaplan–Strömberg 用优先股案例建立真实合同的权利分类；Aghion–Bolton 为经典主讲，Admati–Pfleiderer 为主线延伸并后置较长定价推导；Neher 的完整逆推和 Bolton、Liu、Nanda、Sundaresan（2024）实验设计放在附录，并明确原文复核范围与教学化简。第 5 周核心题为 H5-1 至 H5-4，其余题目为附录选做。学生材料不写预计用时。是否已公开发布，以实际推送和部署记录为准。

核查命令：python3 checks/verify_materials.py --sources-only 独立复算数值；完成渲染与副本同步后，运行 python3 checks/verify_materials.py 核对本地链接、锚点和文件一致性。检查结果写入 checks 下的 JSON 文件。

本轮 LPA 修订统一核心金额为 K=100、GP 出资比例 2%、Carry 20%；同一分配函数下检查努力与双方 PC。独立的风险选择反例和原论文报酬模型分别说明假设，避免将线性报酬系数当作 Carry。第 4 周有 5 道核心题、2 道 ASW 附录选做题。

公式检查：python3 checks/verify_math.py --katex /path/to/katex.min.js，使用现有 Quarto/KaTeX 资产。第 5 周模型、原文出处与教学推导的对应见 [重写审查记录](checks/week5-model-audit.md)。
