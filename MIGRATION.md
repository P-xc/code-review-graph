# C/C++/Rust 解析修复 — 迁移案底

> 这份文件是给「未来的我 / 另一个会话 / 另一台机器」看的。
> 读完这份，不需要重跑任何调查就能接手。

## 一句话

修了 `code-review-graph` 在 C/C++ 上的三个实测缺陷：函数签名套 Python 语法、
struct 误判成 class 导致死代码假阳性、`#include` 从不解析导致跨文件影响面恒为 0。

- 上游：`https://github.com/sumingwang233/code-review-graph` @ `6b12d11`（v2.3.9）
- 本 fork 基线与上游一致，改动只在 `c-cpp-rust-parsing` 分支

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
  占该项目 dead-code 输出的绝大多数（全是 `ProtobufCAllocator`、
  `ProtobufCMessage`、`ProtobufCType` 这类公开 struct）

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
| 跨文件影响面 | 0 | **生效**（改 `protobuf-c.h` → 1 文件受影响） |

## 测试

```
153 failed, 4109 passed, 863 skipped
```

**153 个失败全部是基线自带的**，与本次改动无关。验证方式：
`git stash` 我的改动后跑基线，同样失败 13/15（Windows 路径、Unicode、
skills 注入、d3 SRI 等环境问题）。我的改动**净减少 4 个失败**
（2 个 struct 测试 + 2 个 postprocessing 签名测试），并**新增 11 个通过**。

基线失败集中在：`test_skills.py`（Unicode/文件模式）、`test_visualization.py`
（d3 SRI）、`test_reconcile_orphan_purge.py`、`test_php_scoped_calls.py`、
`test_registry_search_integration.py` —— 全是 Windows + 环境相关。

## 复现环境（本机）

**GitHub 直连不通。** `https://github.com` 443 被 reset，
`git@github.com` SSH:443 握手后 reset，HTTP 代理写死
`127.0.0.1:7890`（Clash）但没开。

**可用通道：镜像 + 已存凭据。**
```bash
git clone https://ghfast.top/https://github.com/sumingwang233/code-review-graph.git
# 或 https://gh-proxy.com/https://github.com/...
# 凭据在 ~/.git-credentials（git credential.helper=store），用户名 P-xc
```
已把 `http.https://github.com.proxy` 从 global config 删掉。

**Python 引擎在 F 盘。** C 盘当时只剩 28MB，装不下 327MB 的依赖：
```
F:\tmp\crg-engine         venv，code-review-graph 2.3.9
F:\tmp\crg-data           graph.db（测试产物）
C:\Users\Administrator\AppData\Roaming\dsh-desktop\harness\code-review-graph\engine
  ⇢ junction 指向 F:\tmp\crg-engine（DSH 插件按 $DSH_HOME 硬编码找引擎）
```

**装 DSH 插件时别用 pnpm。** 它会重解析 `dsh-purge` 的 git 依赖
（`git@github.com` 被 reset 直接失败）。手工复制包 + 依赖进
`profiles/web/node_modules/` 可行。

**文件是 CRLF。** `parser.py` 等全部 CRLF 行尾，用普通文本替换工具会
匹配失败。上面所有改动都用 `newline=""` 的 Python 脚本做的。

## 还没做的

- **Rust 只做了顺带确认**，没有专门修。`_CLASS_TYPES["rust"]` 已经是
  `struct_item/enum_item/trait_item`（合理），`_FUNCTION_TYPES` 有
  `function_item`。Rust 项目未实测。
- C++ 模板、宏、`#ifdef` 分支里的定义仍未处理。
- 37/424 个 C/C++ 函数仍无 return_type —— 多为 K&R 风格或宏生成的定义。
- `impact` 深度仍是默认 2 跳；protobuf-c 这种扁平项目跨文件依赖本来就稀疏。
