"""XtQuant.XtTrade 交易模块 MCP 服务。"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

mcp = FastMCP("XtQuant.XtTrader MCP")

# 全局交易器实例
_trader: Any = None


def _get_trader():
    """获取交易器实例，未初始化时抛出异常。"""
    global _trader
    if _trader is None:
        raise RuntimeError("交易通道未初始化，请先调用 init_trader 初始化连接")
    return _trader


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


def _run(callable_obj, *args, **kwargs) -> dict[str, Any]:
    try:
        result = callable_obj(*args, **kwargs)
        return _ok(result)
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


def _run_with_trader(callable_obj, *args, **kwargs) -> dict[str, Any]:
    """使用交易器实例执行调用。"""
    try:
        trader = _get_trader()
        result = callable_obj(trader, *args, **kwargs)
        return _ok(result)
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


# ============================================================================
# System Setup APIs
# ============================================================================


@mcp.tool()
def init_trader(path: str = "", session_id: int = 0) -> dict[str, Any]:
    """
    初始化交易通道并连接到 MiniQMT。

    输入参数:
        path: str - MiniQMT 客户端路径，默认为空（自动查找）
        session_id: int - 会话 ID，默认为 0

    输出:
        dict[str, Any] - 连接结果
            - 成功: { "ok": true, "data": { "message": "连接成功" } }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        创建 XtQuantTrader 实例并连接到 MiniQMT 客户端。
        连接成功后需调用 start_trader 启动交易线程。
        QMT 客户端需保持登录状态。
    """
    global _trader
    try:
        from xtquant import xttrader as xttrader
    except Exception as exc:
        return _err(f"无法导入 xtquant.xttrader: {exc}")

    try:
        _trader = xttrader.XtQuantTrader(path, session_id)
        return _ok({"message": "交易通道创建成功，请调用 start_trader 启动"})
    except Exception as exc:
        _trader = None
        return _err(f"{type(exc).__name__}: {exc}")


@mcp.tool()
def start_trader() -> dict[str, Any]:
    """
    启动交易线程并准备环境。

    输入参数:
        无

    输出:
        dict[str, Any] - 启动结果
            - 成功: { "ok": true, "data": { "message": "启动成功" } }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        启动交易线程，建立与 MiniQMT 的通信连接。
        初始化完成后即可进行交易操作。
        需先调用 init_trader 初始化交易通道。
    """
    return _run_with_trader(lambda t: t.start())


@mcp.tool()
def connect_trader() -> dict[str, Any]:
    """
    连接到 MiniQMT。

    输入参数:
        无

    输出:
        dict[str, Any] - 连接结果
            - 成功: { "ok": true, "data": 0 }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        建立与 MiniQMT 的 socket 连接。
        返回 0 表示连接成功。
    """
    return _run_with_trader(lambda t: t.connect())


@mcp.tool()
def stop_trader() -> dict[str, Any]:
    """
    停止交易通道。

    输入参数:
        无

    输出:
        dict[str, Any] - 停止结果
            - 成功: { "ok": true, "data": { "message": "已停止" } }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        停止交易线程并关闭连接。
        停止后所有交易操作将不可用。
    """
    return _run_with_trader(lambda t: t.stop())
    global _trader
    _trader = None
    return _ok({"message": "交易通道已停止"})


@mcp.tool()
def set_relaxed_response_order_enabled(enabled: bool = True) -> dict[str, Any]:
    """
    设置是否启用专用线程处理订单响应。

    输入参数:
        enabled: bool - 是否启用，默认为 True

    输出:
        dict[str, Any] - 设置结果

    功能说明:
        启用后，订单响应将在专用线程中处理，提高并发性能。
    """
    return _run_with_trader(lambda t: t.set_relaxed_response_order_enabled(enabled))


@mcp.tool()
def register_trader_callback(callback_type: str = "default") -> dict[str, Any]:
    """
    注册交易回调处理器。

    输入参数:
        callback_type: str - 回调类型，默认为 "default"
            - "default": 使用默认回调处理

    输出:
        dict[str, Any] - 注册结果

    功能说明:
        注册回调类用于接收订单、成交、持仓等推送消息。
        需先初始化交易通道。
    """
    return _run_with_trader(lambda t: t.register_callback(None))


# ============================================================================
# Account Subscription APIs
# ============================================================================


@mcp.tool()
def subscribe_account(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    订阅账户信息（资金、订单、成交、持仓）。

    输入参数:
        account_id: str - 账户 ID，格式为 '客户号.市场'，如 '000000.SZ'
        account_type: str - 账户类型，默认为 "STOCK"（股票）
            - "STOCK": 股票账户
            - "CREDIT": 信用账户
            - "FUTURE": 期货账户

    输出:
        dict[str, Any] - 订阅结果
            - 成功: { "ok": true, "data": 0 }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        订阅指定账户的信息推送。
        订阅后才能接收该账户的资金、订单、成交、持仓的实时更新。
    """
    return _run_with_trader(lambda t: t.subscribe(_make_account(account_id, account_type)))


@mcp.tool()
def unsubscribe_account(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    取消订阅账户信息。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 取消订阅结果

    功能说明:
        取消指定账户的信息订阅。
    """
    return _run_with_trader(lambda t: t.unsubscribe(_make_account(account_id, account_type)))


def _make_account(account_id: str, account_type: str = "STOCK"):
    """创建账户对象。"""
    from xtquant import xttrader as xttrader
    if account_type == "STOCK":
        return xttrader.StockAccount(account_id)
    elif account_type == "CREDIT":
        return xttrader.CreditAccount(account_id)
    elif account_type == "FUTURE":
        return xttrader.FuturesAccount(account_id)
    return xttrader.StockAccount(account_id)


# ============================================================================
# Order APIs
# ============================================================================


@mcp.tool()
def order_stock(
    account_id: str,
    stock_code: str,
    order_type: int,
    order_volume: int,
    price_type: int,
    price: float,
    strategy_name: str = "",
    order_remark: str = "",
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    同步下单（股票）。

    输入参数:
        account_id: str - 账户 ID，格式为 '客户号.市场'
        stock_code: str - 证券代码，如 '600000.SH'
        order_type: int - 订单类型
            - 23: 买入（STOCK_BUY）
            - 24: 卖出（STOCK_SELL）
        order_volume: int - 订单数量（股数）
        price_type: int - 价格类型
            - 5: 最新价（市价，仅实时交易）
            - 11: 限价（FIX_PRICE）
        price: float - 订单价格
        strategy_name: str - 策略名称（可选）
        order_remark: str - 订单备注（最多24字符，可选）
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 下单结果
            - 成功: { "ok": true, "data": <order_id> }，order_id > 0
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        同步下单，返回订单 ID 或 -1（失败）。
        市价单仅在实盘交易有效，模拟交易不支持。
    """
    return _run_with_trader(
        lambda t: t.order_stock(
            _make_account(account_id, account_type),
            stock_code,
            order_type,
            order_volume,
            price_type,
            price,
            strategy_name,
            order_remark,
        )
    )


@mcp.tool()
def order_stock_async(
    account_id: str,
    stock_code: str,
    order_type: int,
    order_volume: int,
    price_type: int,
    price: float,
    strategy_name: str = "",
    order_remark: str = "",
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    异步下单（股票）。

    输入参数:
        同 order_stock

    输出:
        dict[str, Any] - 下单结果
            - 成功: { "ok": true, "data": <seq> }，seq 为序列号
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        异步下单，立即返回序列号。
        订单结果通过回调 on_order_stock_async_response 返回。
    """
    return _run_with_trader(
        lambda t: t.order_stock_async(
            _make_account(account_id, account_type),
            stock_code,
            order_type,
            order_volume,
            price_type,
            price,
            strategy_name,
            order_remark,
        )
    )


@mcp.tool()
def cancel_order_stock(
    account_id: str,
    order_id: int,
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    同步撤单（按订单ID）。

    输入参数:
        account_id: str - 账户 ID
        order_id: int - 订单 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 撤单结果
            - 成功: { "ok": true, "data": 0 }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        同步撤单，按订单ID撤销。
    """
    return _run_with_trader(
        lambda t: t.cancel_order_stock(
            _make_account(account_id, account_type),
            order_id,
        )
    )


@mcp.tool()
def cancel_order_stock_async(
    account_id: str,
    order_id: int,
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    异步撤单（按订单ID）。

    输入参数:
        account_id: str - 账户 ID
        order_id: int - 订单 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 撤单结果

    功能说明:
        异步撤单，立即返回序列号。
    """
    return _run_with_trader(
        lambda t: t.cancel_order_stock_async(
            _make_account(account_id, account_type),
            order_id,
        )
    )


@mcp.tool()
def cancel_order_stock_sysid(
    account_id: str,
    market: int,
    order_sysid: str,
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    同步撤单（按系统编号）。

    输入参数:
        account_id: str - 账户 ID
        market: int - 市场代码（1=上海，0=深圳）
        order_sysid: str - 柜台合同号
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 撤单结果

    功能说明:
        同步撤单，按柜台分配的合同号撤销。
    """
    return _run_with_trader(
        lambda t: t.cancel_order_stock_sysid(
            _make_account(account_id, account_type),
            market,
            order_sysid,
        )
    )


@mcp.tool()
def cancel_order_stock_sysid_async(
    account_id: str,
    market: int,
    order_sysid: str,
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    异步撤单（按系统编号）。

    输入参数:
        account_id: str - 账户 ID
        market: int - 市场代码（1=上海，0=深圳）
        order_sysid: str - 柜台合同号
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 撤单结果

    功能说明:
        异步撤单，立即返回序列号。
    """
    return _run_with_trader(
        lambda t: t.cancel_order_stock_sysid_async(
            _make_account(account_id, account_type),
            market,
            order_sysid,
        )
    )


# ============================================================================
# Fund Transfer
# ============================================================================


@mcp.tool()
def fund_transfer(
    account_id: str,
    transfer_direction: int,
    price: float,
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    资金划转。

    输入参数:
        account_id: str - 账户 ID
        transfer_direction: int - 划转方向
            - 510: 普通资金划往快速资金（FUNDS_TRANSFER_NORMAL_TO_SPEED）
            - 511: 快速资金划往普通资金（FUNDS_TRANSFER_SPEED_TO_NORMAL）
        price: float - 划转金额
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 划转结果
            - 成功: { "ok": true, "data": { "success": true, "message": "<信息>" } }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        在普通资金账户和快速资金账户之间划转资金。
    """
    return _run_with_trader(
        lambda t: t.fund_transfer(
            _make_account(account_id, account_type),
            transfer_direction,
            price,
        )
    )


# ============================================================================
# Query APIs - Stock
# ============================================================================


@mcp.tool()
def query_stock_asset(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询账户资产。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 资产信息
            - 成功: { "ok": true, "data": { "cash": <现金>, "total_asset": <总资产>, ... } }
            - 失败: { "ok": false, "error": "<错误信息>" }

    功能说明:
        查询指定账户的资产信息，包括现金、总资产、冻结资金等。
    """
    return _run_with_trader(
        lambda t: t.query_stock_asset(_make_account(account_id, account_type))
    )


@mcp.tool()
def query_stock_orders(
    account_id: str,
    cancelable_only: bool = False,
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    查询今日订单。

    输入参数:
        account_id: str - 账户 ID
        cancelable_only: bool - 是否仅查询可撤订单，默认为 False
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 订单列表

    功能说明:
        查询今日所有订单或仅可撤订单。
    """
    return _run_with_trader(
        lambda t: t.query_stock_orders(
            _make_account(account_id, account_type),
            cancelable_only,
        )
    )


@mcp.tool()
def query_stock_trades(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询今日成交。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 成交列表

    功能说明:
        查询今日所有成交记录。
    """
    return _run_with_trader(
        lambda t: t.query_stock_trades(_make_account(account_id, account_type))
    )


@mcp.tool()
def query_stock_positions(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询持仓。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    output:
        dict[str, Any] - 持仓列表

    功能说明:
        查询指定账户的所有持仓信息。
    """
    return _run_with_trader(
        lambda t: t.query_stock_positions(_make_account(account_id, account_type))
    )


@mcp.tool()
def query_position_statistics(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询期货持仓统计。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 持仓统计列表

    功能说明:
        查询期货账户的持仓统计信息。
    """
    return _run_with_trader(
        lambda t: t.query_position_statistics(_make_account(account_id, account_type))
    )


# ============================================================================
# Query APIs - Credit
# ============================================================================


@mcp.tool()
def query_credit_detail(account_id: str) -> dict[str, Any]:
    """
    查询信用账户明细。

    输入参数:
        account_id: str - 信用账户 ID

    输出:
        dict[str, Any] - 信用账户明细

    功能说明:
        查询融资融券信用账户的详细信息。
    """
    return _run_with_trader(
        lambda t: t.query_credit_detail(_make_account(account_id, "CREDIT"))
    )


@mcp.tool()
def query_stk_compacts(account_id: str) -> dict[str, Any]:
    """
    查询融资融券合约。

    输入参数:
        account_id: str - 信用账户 ID

    输出:
        dict[str, Any] - 合约列表

    功能说明:
        查询融资融券的所有合约信息。
    """
    return _run_with_trader(
        lambda t: t.query_stk_compacts(_make_account(account_id, "CREDIT"))
    )


@mcp.tool()
def query_credit_subjects(account_id: str) -> dict[str, Any]:
    """
    查询融资标的。

    输入参数:
        account_id: str - 信用账户 ID

    输出:
        dict[str, Any] - 融资标的列表

    功能说明:
        查询可作为融资买入的标的证券。
    """
    return _run_with_trader(
        lambda t: t.query_credit_subjects(_make_account(account_id, "CREDIT"))
    )


@mcp.tool()
def query_credit_slo_code(account_id: str) -> dict[str, Any]:
    """
    查询可融券源。

    输入参数:
        account_id: str - 信用账户 ID

    输出:
        dict[str, Any] - 可融券源列表

    功能说明:
        查询可作为融券卖出的标的证券。
    """
    return _run_with_trader(
        lambda t: t.query_credit_slo_code(_make_account(account_id, "CREDIT"))
    )


@mcp.tool()
def query_credit_assure(account_id: str) -> dict[str, Any]:
    """
    查询担保品。

    输入参数:
        account_id: str - 信用账户 ID

    输出:
        dict[str, Any] - 担保品列表

    功能说明:
        查询账户中的担保品证券。
    """
    return _run_with_trader(
        lambda t: t.query_credit_assure(_make_account(account_id, "CREDIT"))
    )


# ============================================================================
# Query APIs - Other
# ============================================================================


@mcp.tool()
def query_new_purchase_limit(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询新股申购额度。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 申购额度信息

    功能说明:
        查询指定账户的新股申购额度。
    """
    return _run_with_trader(
        lambda t: t.query_new_purchase_limit(_make_account(account_id, account_type))
    )


@mcp.tool()
def query_ipo_data() -> dict[str, Any]:
    """
    查询今日新股信息。

    输入参数:
        无

    输出:
        dict[str, Any] - 今日新股申购信息列表

    功能说明:
        查询今日可申购的新股信息。
    """
    return _run_with_trader(lambda t: t.query_ipo_data())


@mcp.tool()
def query_account_infos() -> dict[str, Any]:
    """
    查询所有账户信息。

    输入参数:
        无

    输出:
        dict[str, Any] - 所有账户信息列表

    功能说明:
        查询当前连接下的所有账户信息。
    """
    return _run_with_trader(lambda t: t.query_account_infos())


@mcp.tool()
def query_account_status() -> dict[str, Any]:
    """
    查询账户状态。

    输入参数:
        无

    输出:
        dict[str, Any] - 所有账户状态列表

    功能说明:
        查询当前连接下所有账户的状态。
    """
    return _run_with_trader(lambda t: t.query_account_status())


@mcp.tool()
def query_com_fund(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询场外基金。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 场外基金信息

    功能说明:
        查询账户持有的场外基金信息。
    """
    return _run_with_trader(
        lambda t: t.query_com_fund(_make_account(account_id, account_type))
    )


@mcp.tool()
def query_com_position(account_id: str, account_type: str = "STOCK") -> dict[str, Any]:
    """
    查询场外基金持仓。

    输入参数:
        account_id: str - 账户 ID
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 场外基金持仓列表

    功能说明:
        查询账户持有的场外基金持仓信息。
    """
    return _run_with_trader(
        lambda t: t.query_com_position(_make_account(account_id, account_type))
    )


@mcp.tool()
def export_data(
    account_id: str,
    result_path: str,
    data_type: str,
    start_time: str = "",
    end_time: str = "",
    user_param: str = "",
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    导出数据到文件。

    输入参数:
        account_id: str - 账户 ID
        result_path: str - 结果文件路径
        data_type: str - 数据类型
        start_time: str - 开始时间，格式为 'YYYYMMDD'
        end_time: str - 结束时间，格式为 'YYYYMMDD'
        user_param: str - 用户自定义参数
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 导出结果

    功能说明:
        将指定数据导出到 CSV 文件。
    """
    return _run_with_trader(
        lambda t: t.export_data(
            _make_account(account_id, account_type),
            result_path,
            data_type,
            start_time,
            end_time,
            user_param,
        )
    )


@mcp.tool()
def query_data(
    account_id: str,
    result_path: str,
    data_type: str,
    start_time: str = "",
    end_time: str = "",
    user_param: str = "",
    account_type: str = "STOCK",
) -> dict[str, Any]:
    """
    查询并读取数据。

    输入参数:
        account_id: str - 账户 ID
        result_path: str - 结果文件路径
        data_type: str - 数据类型
        start_time: str - 开始时间
        end_time: str - 结束时间
        user_param: str - 用户自定义参数
        account_type: str - 账户类型

    输出:
        dict[str, Any] - 查询结果

    功能说明:
        查询数据并读取到内存中。
    """
    return _run_with_trader(
        lambda t: t.query_data(
            _make_account(account_id, account_type),
            result_path,
            data_type,
            start_time,
            end_time,
            user_param,
        )
    )


# ============================================================================
# Securities Lending APIs
# ============================================================================


@mcp.tool()
def smt_query_quoter(account_id: str) -> dict[str, Any]:
    """
    查询券源报价。

    输入参数:
        account_id: str - 账户 ID

    输出:
        dict[str, Any] - 券源报价列表

    功能说明:
        查询可出借的证券来源及报价。
    """
    return _run_with_trader(
        lambda t: t.smt_query_quoter(_make_account(account_id, "CREDIT"))
    )


@mcp.tool()
def smt_negotiate_order_async(
    account_id: str,
    src_group_id: str,
    order_code: str,
    date: str,
    amount: int,
    apply_rate: float,
    dict_param: str = "",
) -> dict[str, Any]:
    """
    协商借券异步订单。

    输入参数:
        account_id: str - 账户 ID
        src_group_id: str - 源合约组 ID
        order_code: str - 订单代码
        date: str - 日期
        amount: int - 数量
        apply_rate: float - 申请费率
        dict_param: str - 其他参数（JSON字符串）

    输出:
        dict[str, Any] - 下单结果

    功能说明:
        申请库存证券出借，异步方式。
    """
    import json
    params = json.loads(dict_param) if dict_param else {}
    return _run_with_trader(
        lambda t: t.smt_negotiate_order_async(
            _make_account(account_id, "CREDIT"),
            src_group_id,
            order_code,
            date,
            amount,
            apply_rate,
            params,
        )
    )


@mcp.tool()
def smt_query_compact(account_id: str) -> dict[str, Any]:
    """
    查询借券合约。

    输入参数:
        account_id: str - 账户 ID

    输出:
        dict[str, Any] - 借券合约列表

    功能说明:
        查询所有的借券合约信息。
    """
    return _run_with_trader(
        lambda t: t.smt_query_compact(_make_account(account_id, "CREDIT"))
    )


# ============================================================================
# Service Entry Point
# ============================================================================


def get_app() -> Any:
    """获取 ASGI 应用，供 uvicorn 等服务器使用。"""
    return mcp.http_app(transport="sse")


def main() -> None:
    """服务入口。"""
    import os
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    main()
