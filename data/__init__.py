"""数据模块:岗位 / 技能 / 课程 / 员工数据采集与模拟(大纲第二节,阶段 1A)。

入口::

    python -m data.collect          # 在线优先,断网自动回退 fixture
    python -m data.collect --offline

结构::

    data/
    ├── collect.py            采集入口(编排 + CLI)
    ├── httpclient.py        HTTP 客户端与三级数据源调度(api→cache→fixture)
    ├── skilllib.py          统一技能库(别名精确归一,模糊归一见阶段 1B)
    ├── positions.py         岗位配置与多源合并
    ├── employees.py          模拟员工生成器(等级 0-4 + Evidence)
    ├── schemas.py           统一 JSON Schema 与校验
    ├── sources/             外部数据源适配(ESCO / O*NET / Microsoft Learn)
    ├── fixtures/            离线 fixture(真实 API 响应裁剪版)
    ├── raw/                 在线拉取的原始缓存(gitignore)
    └── processed/           标准化 JSON 输出(gitignore)
"""
