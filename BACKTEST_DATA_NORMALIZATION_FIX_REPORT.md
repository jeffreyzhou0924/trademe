# 回测数据规范化修复报告（2025-09-19）

问题概述
- 同样参数的回测得到不同结果。根因是服务端为兼容历史多种符号写法，查询真实K线时对符号进行了“变体匹配”，并且未按 `product_type` 过滤，导致现货与永续数据可能混用，命中谁就用谁。

本次修复
- 严格化符号与产品类型：
  - OKX 永续：统一使用 `BASE-QUOTE-SWAP`（如 `BTC-USDT-SWAP`）
  - OKX 现货：优先使用 `BASE/QUOTE`（如 `BTC/USDT`），排除 `-SWAP`
- 查询时强制按 `product_type` 过滤，避免现货/永续串用。
- 下载器在写库时显式写入 `product_type`：`-SWAP` → `futures`，其余 → `spot`。
- 回测结果附带数据指纹 `data_fingerprint`（exchange/symbol_variant/timeframe/product_type/记录数/起止时间），便于复核两次是否使用同一数据集。

涉及文件
- backend/trading-service/app/api/v1/realtime_backtest.py
  - 规范化 `normalize_symbol_for_db`；增加 `product_type` 过滤；输出数据指纹；回测阶段使用命中的规范化符号。
- backend/trading-service/app/services/backtest_engine_stateless.py
  - 查询时恢复 `product_type` 过滤。
- backend/trading-service/app/services/okx_data_downloader_enhanced.py、okx_data_downloader.py
  - 写库时显式设置 `product_type`（futures/spot）。
- backend/trading-service/scripts/backfill_product_type_market_data.py
  - 回填历史 `MarketData.product_type` 的脚本。

如何回填历史数据（一次性操作）
1. 进入服务目录：
   - `cd backend/trading-service`
2. 执行回填：
   - `python scripts/backfill_product_type_market_data.py`
3. 期望输出：
   - 日志包含“回填完成：futures 更新 X 条，spot 更新 Y 条”。

如何自验修复
- 在 AI 对话页选择：OKX + 永续 + BTC/USDT + 固定历史日期（例如 2024-06-01 至 2024-07-01），连续回测两次。
- 结果应完全一致（交易笔数、收益、回撤等），且结果对象包含 `data_fingerprint`。

注意事项
- 若数据库里存在极旧的历史数据格式，服务端仍保留“变体兜底”，但优先级严格受 `exchange + product_type` 约束，不会再误用。

