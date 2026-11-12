# elm-mcp 安装与「获取文件夹树」测试报告

任务：dsh 安装 `D:/1259/demo/elm-mcp` 并测试获取 1259-HSK 项目文件夹树。

## 1. 安装结果
- 源码：`D:/1259/demo/elm-mcp`（elm-mcp v0.4.0），`uv sync` 建 `.venv`（mcp 2.3.0 / httpx / pydantic 2.14.3），Python 3.14.6。
- 凭证：`C:/Users/Yangxiaofeng191526/.elm_creds.json`（url / username / base64 password），由 `Settings.model_post_init` 读取，无需在连接器里注入 env。
- DSH MCP 连接器：`mcp_connector_import_json` 注册 stdio 连接 `json-elm`（name=`elm`），command=`.venv/Scripts/python.exe -m elm_mcp.cli serve`，cwd=包目录，scope=global。状态 healthy，Host 注册 18 个工具。
- 工具前缀 `mcp__elm__*`（list_projects / list_types / list_folders / ...）。venv 位于 `D:/1259` 而非 `%USERPROFILE%/.dsh`，规避了 Low 完整性标签写不了 Temp 的已知坑。

## 2. 测试：获取文件夹树
- 目标项目：任务 URL 的 componentURI `_bXoyADTjEe-xAc0RgQyu0Q` 对应 RM 项目 **1259-HSK**（project-area `_bTwXkDTjEe-xAc0RgQyu0Q`）。
- 通道实测：`mcp__elm__list_folders({project:"1259-HSK"})` 成功返回 **100 个文件夹**，最大深度 4。
- 顶层 4 个分支：HSK Test Specification / HSK SCOPE / HSK Design Specification / HSK SRS。
- 逐层深度分布：depth 1=4, depth 2=21, depth 3=48, depth 4=27。
- 完整数据见 `folder_tree_1259-HSK.json`。

## 3. 排障与代码适配（关键）
- 原 `oslc.list_folders` 直接以 `public_rm:parent=<component URI>` 查 `/rm/folders`，服务器返回 **400**：`NullPointerException: Submitted parameters must contain a Configuration URI.`（该 ELM 启用配置管理，component 不能作顶层父）。
- 可行路径：项目 `services.xml` 的文件夹 QueryCapability 声明父应为 **project-area URI**；先查 root 文件夹，再以 `public_rm:parent=<folder_uri>` 逐级 BFS 展开。
- 已对 `src/elm_mcp/oslc.py` 的 `list_folders()` 做最小适配：保留原主路径（兼容单测 mock），失败时 fallback 到 project-area + BFS，并过滤 ResponseInfo/Description 伪条目。
- 验证：`pytest tests/ -q` → 109 passed；`ruff check src/elm_mcp/oslc.py` → All checks passed!；本地与 MCP 通道均返回同一份 100 节点树。

## 4. 结论
安装与文件夹树测试均通过；MCP 连接器 healthy、18 工具可用，`list_folders` 已能在该配置管理型 ELM 上返回完整文件夹树。
