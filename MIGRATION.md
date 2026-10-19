# 第四批：C++ 类型别名（`using X = Y;`）不产生节点

> 本文件按批倒序追加。最早的第一、二批在文末。

## 触发场景

第三批做完 concept / 变量模板后，回头量了 10 个 clone 项目的 `CALLS` 边未解析率，
想看看剩下的 unresolved 里有没有可修的真缺陷：

```
type_safe       unres=4614/4926 (93%)   top: REQUIRE 1368, SECTION 216,
                                             has_value 214, value 204, int_t 159
optional        unres=1158/1271 (91%)   top: REQUIRE 366, has_value 53, ...
```

大部分是**不该解析**的：测试框架宏（REQUIRE/SECTION/ASSERT_EQ）、标准库
（std::move / size / push_back）、C 库函数（printf / memcpy / free）。

但 `int_t`(159)、`uint_t`(88) 是 **type_safe 自己的类型别名**，项目里有定义、
被大量调用，却完全没有节点。

## 缺陷

`alias_declaration` 在 parser 里只出现在 `_CPP_HEADER_EVIDENCE_TYPES` ——
那个集合的用途是判断 `.h` 是 C 还是 C++，**从不用来建节点**。
与第三批的 concept 完全同一个病。

统计这 10 个项目里的别名数量：

```
foonathan__type_safe     321
mariusbancila__stduuid    93
TartanLlama__optional     40
rigtorp__SPSCQueue         1
                       ------
                         455
```

455 个类型别名全部无节点。别名是代码库**实际使用的类型名**，
没有它既答不了"int_t 是什么"，也找不到"谁在用 int_t"。

## 改了什么

| 位置 | 改动 |
|---|---|
| `_CLASS_TYPES["cpp"]` | 加 `alias_declaration` |
| `_extract_classes` | cpp 的 struct/union/enum/typedef/concept/**alias** 发 `kind="Type"`，留 `extra["cpp_kind"]="alias_declaration"` |

**这次不需要第三批那三个守卫**：`alias_declaration` 不是 `declaration`，
不会进 `_FUNCTION_TYPES` 的函数路径，而且它的名字只有一个 `type_identifier`
子节点——不存在"证明不是函数"或"名字畸形"的问题。

## 修后实测（10 个项目）

Function 数**全部与基线一致**，Type 大幅增加：

| 项目 | Type 基线 → 修后 | 新增 |
|---|---|---|
| type_safe | 154 → **402** | **+248** |
| stduuid | 173 → **265** | +92 |
| optional | 46 → **79** | +33 |
| MPMCQueue | 4 → 7 | +3 |
| SPSCQueue | 5 → 6 | +1 |
| utf8.h | 7 → 8 | +1 |
| Seqlock / partcl / libco / Containers | 不变 | 0 |

节点确认（type_safe）：
```
Type  int_t    types.hpp:189   {"cpp_kind": "alias_declaration"}
Type  uint_t   types.hpp:190   {"cpp_kind": "alias_declaration"}
Type  size_t   types.hpp:186   {"cpp_kind": "alias_declaration"}
```

## 一个诚实的边界

`int_t` 的 **CALLS 边仍然未解析**。原因合理：别名不是函数，
`int_t(...)` 实际是构造函数调用，而 CALL 解析只连 Function 节点。
未解析率 93% → 86%，改善有限但节点本身现在可查询、可导航了。

## 测试

`tests/test_cpp_type_alias.py`（7 个）+ fixture `tests/fixtures/cpp_type_alias/sample.cpp`：
- 命名空间作用域别名（`using int_t = integer<int>;`）
- 别名到基本类型、别名模板（`template <typename T> using ptr = T*;`）
- 嵌套 namespace 内的别名
- **类成员别名**（`struct Wrapper { using value_type = int; }`）
- 别名不得挤掉普通函数、不得改变类的 kind

## 测试状态

```
153 failed, 4122 passed
```
失败数与第三批完全一致（153），新增 7 个通过，零回归。

---

# 第三批：C++20 concept 与变量模板不产生节点

## 触发场景

从桌面清单 `C++开源项目研读清单100个.md`（117 条）里按 API 体积挑出 10 个最小
的 C/C++ 仓库 clone 到 `F:\vsProject`，逐个建图后写了一个 C++11–20 语法探针
`F:\tmp\cpp_probe\modern_cpp.cpp` 压解析器，发现 C++20 的两个核心特性完全没有节点。

## 缺陷 1：concept 不产生节点

```
template <typename T> concept Integral = is_int_v<T>;
template <Integral T> T clamp_value(T v, T lo, T hi);
```

`Integral` 在图里**不存在**。

`concept_definition` 在 parser 里只出现在 `_CPP_HEADER_EVIDENCE_TYPES` ——
那个集合的用途是判断 `.h` 是 C 还是 C++，**从不用来建节点**。

后果：被约束的函数能找到，约束它的 concept 找不到。"这个模板要求什么"无法回答，
`requires_clamp` 无法追溯到 `Integral`。

## 缺陷 2：变量模板被丢弃

```
template <typename T> constexpr bool is_int_v = false;   -> 无节点
template <> constexpr bool is_int_v<int> = true;         -> 无节点
```

走的路径不同：解析成 `template_declaration > declaration > init_declarator > identifier`，
而 `declaration` 在 cpp 的 `_FUNCTION_TYPES` 里，于是被送到 `_extract_functions`。
那里 `_get_name` 调 `_cpp_is_callable_declaration`，`init_declarator` 不是 callable
→ 返回 None → 节点被丢弃，什么都没记下。

讽刺的是：concept 就算修好了能建节点，它引用的 `is_int_v` 仍然不存在，约束照样无法解析。

## 改了什么

| 位置 | 改动 |
|---|---|
| `_CLASS_TYPES["cpp"]` | 加 `concept_definition` |
| `_extract_classes` | cpp/c 的 struct/union/enum/typedef/**concept** 发 `kind="Type"`，留 `extra["cpp_kind"]` |
| `_extract_functions` | `_get_name` 返回 None 时改调新增的 `_extract_cpp_value_declaration` |
| 新增 `_extract_cpp_value_declaration` | 收变量模板/命名空间常量，发 `kind="Type"` + `extra["cpp_kind"]="variable_template"` |
| 新增 `_cpp_declaration_is_local` | 父链上有 function_definition/lambda/compound_statement 就跳过 |
| 新增 `_cpp_has_const_qualifier` | 要求 constexpr/constinit/const |
| 新增 `_cpp_declarator_is_function` | declarator 链含 function_declarator/parameter_list 就不收 |
| 新增模块级 `_CPP_IDENTIFIER_RE` | 名字必须是合法标识符 |

## 三个必须同时存在的守卫（都是踩出来的）

### 守卫 1：排除函数内局部变量
第一版把 `void f() { int total = 0; }` 里的 `total`、`i` 以及 main 里所有局部变量
都标成了 `variable_template`。walker **会递归进函数体**，我原先假设它只在顶层派发——错的。
修：`_cpp_declaration_is_local` 检查父链。

### 守卫 2：必须证明「不是函数」才收
加了守卫 1 之后，`tl::optional` 的 **41 个方法全部消失**（map / and_then /
transform / or_else / map_or），整个 monadic 接口没了。

这些方法的形状是：
```cpp
template <class F>
TL_OPTIONAL_11_CONSTEXPR decltype(optional_map_impl(std::declval<optional &>(), ...))
map(F &&f) & { ... }
```
在 `template_declaration` 里 + 带 constexpr → 我的守卫放行；
而 `_get_name` 对它们**本来就会返回 None**（尾置 ref-qualifier + decltype 返回
让 callable 探测失败），于是被我当成常量收走。

**教训：`_get_name` 失败不等于"这是常量"。** 修：`_cpp_declarator_is_function`
主动检查 declarator 链，是函数就让路。

### 守卫 3：名字必须是合法标识符
修完守卫 2 后仍掉 41 个。抓到一个名字是**整个模板头**的节点：
```
"template <\r\n      class U = T,\r\n      detail::enable_if_t<...>"
```
来自默认模板参数——`declarator` 字段取到的是参数列表不是 identifier。

单独 parse 时 226 个 Function 全在，但 build 合并后只剩 224：名字不是标识符
就没法当稳定的合并键，把兄弟节点一起拖掉了。修：`_CPP_IDENTIFIER_RE.fullmatch`。

## 修后实测

### 语法探针 `F:\tmp\cpp_probe\modern_cpp.cpp`
| | 修前 | 修后 |
|---|---|---|
| `Integral`（concept） | 缺失 | **Type @ L62** |
| `is_int_v`（变量模板） | 缺失 | **Type @ L47** |
| 局部变量 total/i/a/h/... | — | **全部 clean**（未被误收） |
| 总节点 | 26 | **28**（只多该多的 2 个） |

### 10 个 clone 项目（对照基线 = 第一批修复后的 parser.py）
Function 数**全部与基线一致**，只新增该增的 Type：

| 项目 | Function 基线/修后 | 新增 variable_template |
|---|---|---|
| Seqlock | 5 / 5 | 0 |
| partcl | 42 / 42 | 0 |
| MPMCQueue | 28 / 28 | 1 |
| SPSCQueue | 23 / 23 | 0 |
| libco | 151 / 151 | 0 |
| utf8.h | 93 / 93 | 0 |
| stduuid | 1703 / 1703 | 17 |
| optional | 265 / 265 | 4 |
| Containers | 373 / 373 | 0 |
| type_safe | 907 / 907 | 5 |

concept 全是 0 —— 这 10 个项目是 C++11/14/17，本来就没用 C++20 concept，符合预期。

## 对比方法（重要，我在这栽过）

**不能用 `git stash` 整个 parser.py 当基线** —— parser.py 同时含第一批（struct→Type）
和第三批改动，stash 会把两批一起去掉，得出假的"节点数变化"。

正确做法：`git show c18ea3d:code_review_graph/parser.py` 取出第一批提交时的
parser.py 作为基线，它含第一批、不含第三批。

## 新增测试

`tests/test_cpp20_concepts.py`（6 个）+ fixture `tests/fixtures/cpp_cpp20_concepts/sample.cpp`：
- concept 产生节点且 kind=Type
- 变量模板产生节点
- 被约束的函数仍是 Function
- **尾置 ref-qualifier 的成员方法不被当成变量模板**（守卫 2 的回归测试）
- 普通方法不受影响
- **没有任何节点的名字是畸形**（守卫 3 的回归测试）

## 测试状态

```
153 failed, 4115 passed
```
失败数与上批完全一致（153），新增 6 个通过，零回归。

---

# 第三批：C++20 concept 与变量模板不产生节点

> 本文件按顺序追加每批修复。前两批见下方历史段落。

## 触发场景

从桌面清单 `C++开源项目研读清单100个.md`（117 条）里按 API 体积挑出 10 个最小
的 C/C++ 仓库 clone 到 `F:\vsProject`，逐个建图后写了一个 C++11–20 语法探针
`F:\tmp\cpp_probe\modern_cpp.cpp` 压解析器，发现 C++20 的两个核心特性完全没有节点。

## 缺陷 1：concept 不产生节点

```
template <typename T> concept Integral = is_int_v<T>;
template <Integral T> T clamp_value(T v, T lo, T hi);
```

`Integral` 在图里**不存在**。

`concept_definition` 在 parser 里只出现在 `_CPP_HEADER_EVIDENCE_TYPES` ——
那个集合的用途是判断 `.h` 是 C 还是 C++，**从不用来建节点**。

后果：被约束的函数能找到，约束它的 concept 找不到。"这个模板要求什么"无法回答，
`requires_clamp` 无法追溯到 `Integral`。

## 缺陷 2：变量模板被丢弃

```
template <typename T> constexpr bool is_int_v = false;   -> 无节点
template <> constexpr bool is_int_v<int> = true;         -> 无节点
```

走的路径不同：解析成 `template_declaration > declaration > init_declarator > identifier`，
而 `declaration` 在 cpp 的 `_FUNCTION_TYPES` 里，于是被送到 `_extract_functions`。
那里 `_get_name` 调 `_cpp_is_callable_declaration`，`init_declarator` 不是 callable
→ 返回 None → 节点被丢弃，什么都没记下。

讽刺的是：concept 就算修好了能建节点，它引用的 `is_int_v` 仍然不存在，约束照样无法解析。

## 改了什么

| 位置 | 改动 |
|---|---|
| `_CLASS_TYPES["cpp"]` | 加 `concept_definition` |
| `_extract_classes` | cpp/c 的 struct/union/enum/typedef/**concept** 发 `kind="Type"`，留 `extra["cpp_kind"]` |
| `_extract_functions` | `_get_name` 返回 None 时改调新增的 `_extract_cpp_value_declaration` |
| 新增 `_extract_cpp_value_declaration` | 收变量模板/命名空间常量，发 `kind="Type"` + `extra["cpp_kind"]="variable_template"` |
| 新增 `_cpp_declaration_is_local` | 父链上有 function_definition/lambda/compound_statement 就跳过 |
| 新增 `_cpp_has_const_qualifier` | 要求 constexpr/constinit/const |
| 新增 `_cpp_declarator_is_function` | declarator 链含 function_declarator/parameter_list 就不收 |
| 新增模块级 `_CPP_IDENTIFIER_RE` | 名字必须是合法标识符 |

## 三个必须同时存在的守卫（都是踩出来的）

### 守卫 1：排除函数内局部变量
第一版把 `void f() { int total = 0; }` 里的 `total`、`i` 以及 main 里所有局部变量
都标成了 `variable_template`。walker **会递归进函数体**，我原先假设它只在顶层派发——错的。
修：`_cpp_declaration_is_local` 检查父链。

### 守卫 2：必须证明「不是函数」才收
加了守卫 1 之后，`tl::optional` 的 **41 个方法全部消失**（map / and_then /
transform / or_else / map_or），整个 monadic 接口没了。

这些方法的形状是：
```cpp
template <class F>
TL_OPTIONAL_11_CONSTEXPR decltype(optional_map_impl(std::declval<optional &>(), ...))
map(F &&f) & { ... }
```
在 `template_declaration` 里 + 带 constexpr → 我的守卫放行；
而 `_get_name` 对它们**本来就会返回 None**（尾置 ref-qualifier + decltype 返回
让 callable 探测失败），于是被我当成常量收走。

**教训：`_get_name` 失败不等于"这是常量"。** 修：`_cpp_declarator_is_function`
主动检查 declarator 链，是函数就让路。

### 守卫 3：名字必须是合法标识符
修完守卫 2 后仍掉 41 个。抓到一个名字是**整个模板头**的节点：
```
"template <\r\n      class U = T,\r\n      detail::enable_if_t<...>"
```
来自默认模板参数——`declarator` 字段取到的是参数列表不是 identifier。

单独 parse 时 226 个 Function 全在，但 build 合并后只剩 224：名字不是标识符
就没法当稳定的合并键，把兄弟节点一起拖掉了。修：`_CPP_IDENTIFIER_RE.fullmatch`。

## 修后实测

### 语法探针 `F:\tmp\cpp_probe\modern_cpp.cpp`
| | 修前 | 修后 |
|---|---|---|
| `Integral`（concept） | 缺失 | **Type @ L62** |
| `is_int_v`（变量模板） | 缺失 | **Type @ L47** |
| 局部变量 total/i/a/h/... | — | **全部 clean**（未被误收） |
| 总节点 | 26 | **28**（只多该多的 2 个） |

### 10 个 clone 项目（对照基线 = 第一批修复后的 parser.py）
Function 数**全部与基线一致**，只新增该增的 Type：

| 项目 | Function 基线/修后 | 新增 variable_template |
|---|---|---|
| Seqlock | 5 / 5 | 0 |
| partcl | 42 / 42 | 0 |
| MPMCQueue | 28 / 28 | 1 |
| SPSCQueue | 23 / 23 | 0 |
| libco | 151 / 151 | 0 |
| utf8.h | 93 / 93 | 0 |
| stduuid | 1703 / 1703 | **17** |
| optional | 265 / **265** | 4 |
| Containers | 373 / 373 | 0 |
| type_safe | 907 / 907 | **5** |

concept 全是 0 —— 这 10 个项目是 C++11/14/17，本来就没用 C++20 concept，符合预期。

## 对比方法（重要，我在这栽过）

**不能用 `git stash` 整个 parser.py 当基线** —— parser.py 同时含第一批（struct→Type）
和第三批改动，stash 会把两批一起去掉，得出假的"节点数变化"。

正确做法：`git show c18ea3d:code_review_graph/parser.py` 取出第一批提交时的
parser.py 作为基线，它含第一批、不含第三批。

## 新增测试

`tests/test_cpp20_concepts.py`（6 个）+ fixture `tests/fixtures/cpp_cpp20_concepts/sample.cpp`：
- concept 产生节点且 kind=Type
- 变量模板产生节点
- 被约束的函数仍是 Function
- **尾置 ref-qualifier 的成员方法不被当成变量模板**（守卫 2 的回归测试）
- 普通方法不受影响
- **没有任何节点的名字是畸形**（守卫 3 的回归测试）

## 测试状态

```
153 failed, 4115 passed
```
失败数与上批完全一致（153），新增 6 个通过，零回归。

---

# 仓库/环境备忘（承接上文）

## clone 的 10 个项目

`F:\vsProject\<owner>__<repo>`（`/` 换成 `__`，因为 Windows 路径）：
```
rigtorp__Seqlock        zserge__partcl        rigtorp__MPMCQueue
rigtorp__SPSCQueue      Tencent__libco        sheredom__utf8.h
mariusbancila__stduuid  TartanLlama__optional bkthomps__Containers
foonathan__type_safe
```
图数据在 `F:\tmp\scan\<repo>_base` / `_fixed`（base = 第一批后的基线）。

体积探测结果在 `F:\tmp\repo_sizes.json`（117 个仓库的 API size）。
最小的几个：Seqlock 0.02MB、partcl 0.03MB、MPMCQueue 0.08MB、SPSCQueue 0.17MB、
libco 0.19MB。

## 第三方测试头会污染统计

`mariusbancila__stduuid` 11 个文件出了 2039 个节点，因为
`catch/catch.hpp` 单文件就 1891 个节点。`utf8.h` 的 `test/utest.h` 同理。
扫自有代码前要排除 `vendor/`、`test/`、`catch/` 这类第三方头，否则
dead-code 和大函数统计全是噪声。


---



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
