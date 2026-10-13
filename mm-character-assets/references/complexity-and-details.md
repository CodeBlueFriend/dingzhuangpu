# 复杂度与细节覆盖

六个维度各取 0–2：服装层次、头部造型、纹样材质、配饰道具、左右差异、遮挡背面。总分 0–3 为 `simple`，4–7 为 `medium`，8–12 为 `complex`。

评分只帮助规划，不能覆盖明确要求：

- 用户点名的细节必须进入覆盖表。
- 左右不同必须能看清两侧；不能镜像。
- 复杂后发型必须展示后脑或头饰背面。
- 已在主视图清楚可见的构件不重复占细节格。
- 陌生且必需的结构没有参考时保持 `unresolved`，不能直接进入 `spec_locked`。

每个重要部件记录 `part_id / required_by / anatomical_side / attachment_location / visible_in / occluded_in / coverage_cells / detail_priority / reference_source / qa_status`。

细节选择顺序：用户点名与结构必需项 → 主视图看不清的信息 → 装饰性展示。默认只覆盖约定的可见资产信息，不自动生成服装拆解、隐藏缝线或悬浮零件图。
