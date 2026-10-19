> 这份文件是给「未来的我 / 另一个会话 / 另一台机器」看的。
> 读完这份，不需要重跑任何调查就能接手。

## 一句话

修了 `code-review-graph` 在 C/C++ 上的三类缺陷，以及一个让 19 个子命令读不到外部图的 CLI 缺陷。

- 上游：`https://github.com/sumingwang233/code-review-graph` @ `6b12d11`（v2.3.9）
- 本 fork：`https://github.com/P-xc/code-review-graph`，分支 `c-cpp-rust-parsing`
- PR：https://github.com/sumingwang233/code-review-graph/pull/1 → base `staging`

---

# 第一批：C/C++ 解析（commit c18ea3d）

## 被测项目

`F:\vsProject\protobuf-c` — C 项目，116 文件 / 40 源文件 / git `8c201f6` master。
43 文件入图，690 节点 / 4223 边，build 约 3 秒。

## 三个缺陷（修前实测数据）

### 缺陷 1：C/C++ 函数签名是 Python 语法

```
signature = "def protobuf_c_message_unpack()"
params = None
return_type = None
```

**424/424** 个 C/C++ Function 节点全部如此。

根因两处叠加：
1. `_get_params` / `_get_return_type` 只做**扁平子节点扫描**。tree-sitter-c 把
   `parameter_list` 放在 `function_declarator` 里，可能再套一层
   `pointer_declarator`，扁平扫描永远够不着 → 恒为 `None`。
2. 三处签名渲染（两处在 `tools/build.py`，一处在 `postprocessing.py`）无条件
   拼 `f"def {name}({params or ''})"`。params 为 None 就渲染成 `def f()` ——
   看起来像完整答案，实际是"从没解析过"。

### 缺陷 2：C struct / enum / union 被判成 Class

`_CLASS_TYPES["c"] = ["struct_specifier", "type_definition"]`，于是 39 个 C 类型
声明全部 `kind="Class"`。后果：

- 渲染成 `class ProtobufCMessage`，不是 C
- dead-code 把类型声明当成"无引用的 class" → **134 项**假阳性，
  占该项目 dead-code 输出的绝大多数

### 缺陷 3：跨文件影响面恒为 0

```
impact --files protobuf-c/protobuf-c.c
  → 93 nodes directly changed, 0 nodes impacted, 0 additional files
```

真因：`_do_resolve_module` **没有 c/cpp 分支**，直接 `return None`，
于是 `IMPORTS_FROM` 边的 target 保留裸字符串 `protobuf-c.h`。
裸字符串不是任何节点的 qualified name，遍历一步都跨不出去。

佐证：`cross-file CALLS = 0`，98 条 IMPORTS_FROM 全是悬空边。

## 改了什么

| 文件 | 改动 |
|---|---|
| `parser.py` | 新增 `_c_cpp_parameter_list` / `_c_cpp_return_type` / `_resolve_c_cpp_include`；`_get_params`、`_get_return_type` 对 c/cpp 分派；`_extract_import_specs` 传 include 的 quote/angle 形式；`_extract_classes` 对 c/cpp 的 struct/union/enum/typedef 发 `kind="Type"` 并留 `extra["c_kind"]` |
| `build.py` | 新增共用 `render_signature` / `normalize_params`，替换两处重复的 `def` 拼接；签名按语言分派 |
| `postprocessing.py` | 签名计算改用共用函数 |
| `graph.py` | `get_nodes_without_signature` 多取 `language` 列 |
| `tests/test_multilang.py` | C/XS struct 断言改 `Type`；新增 2 个 C 签名/类型测试 |
| `tests/test_c_include_resolution.py` | **新增**，5 个 include 解析测试 |
| `tests/fixtures/c_include_resolution/` | **新增**，C include fixture |

### 关键设计决定

**Python 保留 `def` 形式。** 第一版把 `def` 对所有语言都去掉了，直接
弄坏 `test_function_signature_format`（Python 的 `def f() -> R` 是字面正确的
源码形式）。改成：`language == "python"` 走 `def`，其余走 C 家族形式。
签名渲染因此必须知道语言，`get_nodes_without_signature` 才加了 `language` 列。

**返回类型保留 `*` 和 `const`。** `const char *protobuf_c_version(void)`
一开始返回 `char`——循环在第一个 declarator 就 break 了，而 `*` 是
`pointer_declarator` 的匿名子节点。现在在 break 前先收集匿名子节点。
同时 `type_qualifier`（const/volatile）修饰的是**返回类型**不是函数，
所以不再丢弃。

**include 搜索顺序跟编译器一致。** `#include "x.h"` 先查包含者所在目录，
再向上走到仓库根；`#include <x.h>` 只向上走。系统头（`stdio.h`）保持裸字符串
——它不是节点，不该变成边 target。全程 `._repo_root` 夹取，不会逃出仓库。

**C++ 的 `class_specifier` 仍是 Class。** 只有 struct/union/enum/typedef 转 Type。

## 修后实测（protobuf-c）

| 指标 | 修前 | 修后 |
|---|---|---|
| C/C++ `def f()` 签名 | 424/424 | **0/424** |
| `protobuf_c_message_unpack` 签名 | `def protobuf_c_message_unpack()` | `ProtobufCMessage * protobuf_c_message_unpack(const ProtobufCMessageDescriptor *desc, ProtobufCAllocator *allocator, size_t len, const uint8_t *data)` |
| 有 return_type 的 C/C++ 函数 | 0/424 | **387/424** |
| C 节点 `kind="Class"` | 39 | **0**（全转 Type） |
| dead-code 总数 | 134 | **104**（剩的是 C++ 真 class + C static 函数） |
| IMPORTS_FROM 裸字符串 | 98 | **0** |
| 跨文件影响面 | 0 | **生效** |

---

# 第二批：--data-dir 对 19 个子命令失效

## 现象

用外部目录建图后，绝大多数读命令**静默返回空**：

```
$ build --repo <json-c> --data-dir F:\tmp\scan\x     # 645 节点
$ status --repo <json-c> --data-dir F:\tmp\scan\x    # 645 节点  ✓
$ search "json_object" --repo <json-c>               # Found 0, search_mode "none"
```

`search_mode: "none"` 是破绽：FTS 表不存在，因为**根本没图**。
同一份图，`status` 答 645 节点，`search` 答 0，且都报 `status: "ok"`。

## 根因（两层）

1. **参数缺失**：29 个子命令只有 10 个声明了 `--data-dir`。
   `search --data-dir X` 直接被拒：`unrecognized arguments`。
2. **解析绕过**（真正的）：即使声明了参数也没用。`query/impact/search/flows/
   flow/communities/community/architecture/large-functions/refactor` 这 10 个
   在 `_GRAPH_TOOL_COMMANDS` 分支里**提前 return**，走自己的
   `db_path = get_db_path(repo_root)` —— 永远解析到
   `<repo>/.code-review-graph/graph.db`，完全不看 `--data-dir`。
   而工具层 `_get_store(repo_root)` 也是 `get_db_path(root)`，
   没有任何通道能传入外部路径。

## 改了什么

| 文件 | 改动 |
|---|---|
| `cli.py` | 给 15 个命令加 `--data-dir`（随后移除 install/init 两个，它们不读图）；`_data_dir_cmds` 白名单扩到 22 个；`_read_only_db_cmds` 扩到 19 个；`_GRAPH_TOOL_COMMANDS` 分支的 `db_path` 解析改为优先 `--data-dir`；`_run_graph_tool_command` 新增 `db_path` 形参并转发给 10 个工具调用 |
| `tools/_common.py` | `_get_store` 新增可选 `db_path`（默认 None，26 处既有调用行为不变） |
| `tools/query.py` | `query_graph` / `get_impact_radius` / `semantic_search_nodes` / `find_large_functions` 加 `db_path` 并转发 |
| `tools/flows_tools.py` | `list_flows` / `get_flow` 同上 |
| `tools/community_tools.py` | `list_communities_func` / `get_community_func` / `get_architecture_overview_func` 同上 |
| `tools/refactor_tools.py` | `refactor_func` 同上 |
| `tests/test_cli_tool_commands.py` | 期望调用里加 `db_path` |
| `tests/test_tools.py`、`tests/test_agent_transparency.py` | 5 处 `_get_store` mock 的 lambda 加 `db_path=None` |

### 设计决定

**纯读命令绝不创建文件。** 显式 `--data-dir` 直接当路径用，不 `mkdir`、
不建 registry 条目；图不存在就报错，绝不静默造一个空库
（延续 #777 / #782 / #803 的约定）。

**`_get_store` 用可选参数而非必填。** 26 处既有调用一行不改，
只有 CLI 传值，风险面最小。

## 修后实测（json-c，图在 `F:\tmp\scan\jsoncjsonc01820240915`）

| 命令 | 修前 | 修后 |
|---|---|---|
| search | 0（mode=none） | **20**（mode=fts） |
| flows | 0 | **91** |
| communities | 0 | **23** |
| architecture | 0 communities | **23 communities** |
| large-functions | 0 | **50** |
| query | not_found | **17 候选（正常消歧）** |

---

# 9 个 C/C++ 项目扫描验证

`F:\vsProject` 下 9 个项目全部建图成功：

| 项目 | 文件 | 节点 | 边 | return_type 解析率 | 假 `def` 签名 |
|---|---|---|---|---|---|
| json-c 0.18 | 83 | 1166 | 8994 | 99% | 0 |
| liquibook | 66 | 889 | 9064 | 73% | 0 |
| struct2json 1.0.4 | 10 | 87 | 379 | 100% | 0 |
| lolskin (R3nzSkin) | 65 | 3588 | 20737 | 93% | 0 |
| Valorant SkinChanger | 64 | 10743 | 21704 | 95% | 0 |
| Orbitex | 30 | 2701 | 14995 | 94% | 0 |
| MFCApplication | 9 | 35 | 100 | 61% | 0 |
| MFCApplication1 | 9 | 35 | 100 | 61% | 0 |
| MFCApplication2 | 9 | 37 | 104 | 65% | 0 |

未解析的 `IMPORTS_FROM` 全部是系统头（`stdio.h`/`assert.h`/`errno.h`）——
**正确行为**，它们不是仓库内节点。

## 扫描时踩的坑

**项目必须有根目录标记。** 只有 `protobuf-c`、`AduSkin` 等少数有 `.git`。
其余项目要先建 `.code-review-graph/` 空目录，否则
`ValueError: repo_root does not look like a project root`。
已在 9 个项目下建了这个目录（只是标记，不含数据）。

**dead-code 会被 `build/`、`doc/`、第三方库污染。** 首次扫 json-c 时
结果里混进 `doc/html/jquery.js`、`build/CMakeFiles/...`。
扫自有代码前先排除这些目录。

**FTS 是跨列匹配。** `search "main"` 在 Valorant 项目返回 3539 个
（= 全部节点），因为 `file_path` 里含项目名 `...-main`。
这不是 bug，但短词搜索要看 `qualified_name` 而不是总数。

---

# 复现环境（本机）

**GitHub 直连不通。** `https://github.com` 443 被 reset，
`git@github.com` SSH:443 握手后 reset，HTTP 代理写死
`127.0.0.1:7890`（Clash）但没开。

**可用通道**：
- `git clone` → 镜像：`https://ghfast.top/https://github.com/...`
  或 `https://gh-proxy.com/https://github.com/...`
  （**镜像只读，`git push` 静默失败且不报错**）
- `api.github.com` → **直连 200 可用**。所以 fork、push、开 PR 全走 REST API：
  建 fork 用 `POST /repos/{owner}/{repo}/forks`；
  push 用 `git/blobs` → `git/trees` → `git/commits` → `git/refs` 四步，
  tree sha 与本地一致即成功。凭据在 `~/.git-credentials`
  （`git credential.helper=store`），用户名 `P-xc`。
- 已把 `http.https://github.com.proxy` 从 global config 删掉。

**Python 引擎在 F 盘。** C 盘当时只剩 28MB，装不下 327MB 的依赖：
```
F:\tmp\crg-engine         venv，code-review-graph 2.3.9，以 -e 装到 F:\tmp\crg-fork
F:\tmp\crg-fork           修改中的源码（分支 c-cpp-rust-parsing）
F:\tmp\scan\<project>     各项目扫描产物 graph.db
C:\Users\Administrator\AppData\Roaming\dsh-desktop\harness\code-review-graph\engine
  ⇢ junction 指向 F:\tmp\crg-engine（DSH 插件按 $DSH_HOME 硬编码找引擎）
```

**装 DSH 插件时别用 pnpm。** 它会重解析 `dsh-purge` 的 git 依赖
（`git@github.com` 被 reset 直接失败）。手工复制包 + 依赖进
`profiles/web/node_modules/` 可行。

**文件是 CRLF。** `parser.py`、`cli.py` 等全部 CRLF 行尾，用普通文本替换工具会
匹配失败。所有改动都用 `newline=""` 的 Python 脚本做的。
写这类脚本时**带变量名**做替换锚点——第一版漏了接收者，生成了 15 个裸
`add_argument(...)`，CLI 启动时必 NameError。

---

# 测试状态

```
153 failed, 4109 passed, 863 skipped
```

**153 个失败全部是基线自带的**，与改动无关。验证方式：`git stash` 后跑基线，
同一批测试同样失败（Windows 路径分隔符、`/` vs `\`、Unicode、skills 注入、
d3 SRI 等环境问题）。

几个已确认的基线失败组：
- `tests/test_skills.py` — Unicode / 文件模式
- `tests/test_visualization.py` — d3 SRI 校验
- `tests/test_reconcile_orphan_purge.py`、`test_php_scoped_calls.py`
- `tests/test_agent_transparency.py::TestSymbolDisambiguation` — 9 个，路径分隔符
- `tests/test_cli.py::TestGraphToolExplicitRepoResolution` — 1 个

第一批改动净减 4 个失败、新增 11 个通过；第二批零新增。

---

# 还没做的

- **Rust 只做了顺带确认，没有专门修。** `_CLASS_TYPES["rust"]` 已是
  `struct_item/enum_item/trait_item`（合理），`_FUNCTION_TYPES` 有
  `function_item`。**Rust 项目未实测。**
- C++ 模板、宏、`#ifdef` 分支里的定义仍未处理。
- 各项目仍有 0–27% 的 C/C++ 函数没有 return_type（K&R 风格或宏生成）。
- `impact` 深度仍是默认 2 跳；扁平项目（protobuf-c）跨文件依赖本来就稀疏。
- C/C++ 的 `CALLS` 边 unresolved 率 51–100%（MFC 三个是 100%），
  未深入排查——可能与宏、函数指针、COM/MFC 消息映射有关。
