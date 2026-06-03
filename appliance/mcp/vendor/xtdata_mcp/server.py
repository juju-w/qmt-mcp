from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

mcp = FastMCP("XtQuant.XtData MCP")


def _xtdata():
    """
    延迟导入 xtquant.xtdata，避免在未安装 xtquant 的环境下启动即崩溃。
    """
    try:
        from xtquant import xtdata  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "无法导入 xtquant.xtdata。请先安装并配置 QMT/xtquant 运行环境。"
        ) from exc
    return xtdata


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


def _run(callable_obj, *args, **kwargs) -> dict[str, Any]:
    try:
        result = callable_obj(*args, **kwargs)
        return _ok(result)
    except Exception as exc:  # pragma: no cover
        return _err(f"{type(exc).__name__}: {exc}")


@mcp.tool()
def get_full_tick(code_list: list[str]) -> dict[str, Any]:
    """
    获取当前全推市场快照数据。

    输入参数:
        code_list: list[str] - 市场代码列表或合约代码列表。
            - 传市场代码如 ['SH', 'SZ'] 可获取全市场快照
            - 传具体合约如 ['600000.SH', '000001.SZ'] 可获取指定合约快照

    输出:
        dict[str, Any] - 字典，key 为股票代码，value 为该股票的快照数据（numpy 数组或列表）。
            返回格式示例：{ '600000.SH': {...}, '000001.SZ': {...} }

    功能说明:
        获取当前交易日全市场或指定合约的逐笔/切面快照数据。
        数据按时间升序排列。适合用于实时行情监控和盘口分析。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_full_tick, code_list)


@mcp.tool()
def get_market_data(
    field_list: list[str] | None = None,
    stock_list: list[str] | None = None,
    period: str = "1d",
    start_time: str = "",
    end_time: str = "",
    count: int = -1,
    dividend_type: str = "none",
    fill_data: bool = True,
) -> dict[str, Any]:
    """
    从缓存获取行情数据（主要接口）。

    输入参数:
        field_list: list[str] | None - 要获取的字段列表，默认为空（返回所有字段）。
            常见字段：'open'（开盘价）、'high'（最高价）、'low'（最低价）、'close'（收盘价）、
            'volume'（成交量）、'amount'（成交额）、'turn'（换手率）等
        stock_list: list[str] | None - 股票代码列表，格式为 '代码.市场'，如 ['600000.SH', '000001.SZ']
        period: str - K线周期，默认为 '1d'。
            可选值：'tick'（逐笔）、'1m'（1分钟）、'5m'（5分钟）、'15m'、'30m'、'1h'（60分钟）、
            '1d'（日线）、'1w'（周线）、'1mon'（月线）、'1q'（季线）、'1hy'（半年线）、'1y'（年线）
        start_time: str - 起始时间，格式为 'YYYYMMDD' 或 'YYYYMMDDHHmmSS'，如 '20240101'
        end_time: str - 结束时间，格式同 start_time，默认为空（到最新）
        count: int - 数据条数。>=0 时以 end_time 为基准向前取 count 条；-1 时返回所有数据，忽略 end_time
        dividend_type: str - 复权类型，默认为 'none'（不复权）。
            可选值：'none'（不复权）、'front'（前复权）、'back'（后复权）、
            'front_ratio'（前复权比例）、'back_ratio'（后复权比例）
        fill_data: bool - 是否填充数据（处理停牌期间的数据），默认为 True

    输出:
        dict[str, Any] - 字典格式：
            - K线周期（1m/5m/1d等）：返回 { field: pd.DataFrame }，stock_list 为 index，time_list 为 columns
            - 逐笔（tick）：返回 { stock: np.ndarray }，按时间升序排列

    功能说明:
        从内存缓存中快速读取行情数据，是获取历史 K 线和逐笔数据的核心接口。
        数据已加载到缓存中时调用此函数效率最高。未下载的数据需先调用 download_history_data。
    """
    xtdata = _xtdata()
    return _run(
        xtdata.get_market_data,
        field_list or [],
        stock_list or [],
        period,
        start_time,
        end_time,
        count,
        dividend_type,
        fill_data,
    )


@mcp.tool()
def get_local_data(
    field_list: list[str] | None = None,
    stock_list: list[str] | None = None,
    period: str = "1d",
    start_time: str = "",
    end_time: str = "",
    count: int = -1,
    dividend_type: str = "none",
    fill_data: bool = True,
    data_dir: str = "",
) -> dict[str, Any]:
    """
    从本地数据文件直接读取行情数据。

    输入参数:
        field_list: list[str] | None - 要获取的字段列表，默认为空（返回所有字段）
        stock_list: list[str] | None - 股票代码列表，格式为 '代码.市场'，如 ['600000.SH', '000001.SZ']
        period: str - K线周期，默认为 '1d'。可选值同 get_market_data
        start_time: str - 起始时间，格式为 'YYYYMMDD'，如 '20240101'
        end_time: str - 结束时间，格式同 start_time
        count: int - 数据条数。>=0 时以 end_time 为基准向前取 count 条；-1 时返回所有数据
        dividend_type: str - 复权类型，默认为 'none'。可选值同 get_market_data
        fill_data: bool - 是否填充数据，默认为 True
        data_dir: str - 自定义本地数据目录路径，默认为空（使用 xtdata 默认目录）

    输出:
        dict[str, Any] - 字典格式同 get_market_data：
            - K线周期：返回 { field: pd.DataFrame }
            - 逐笔（tick）：返回 { stock: np.ndarray }

    功能说明:
        直接从本地数据文件读取行情数据，跳过内存缓存，适合大批量数据读取场景。
        仅支持 Level-1 数据（1分钟及以上周期的K线）。数据需先通过 download_history_data 下载。
    """
    xtdata = _xtdata()
    kwargs = {
        "field_list": field_list or [],
        "stock_list": stock_list or [],
        "period": period,
        "start_time": start_time,
        "end_time": end_time,
        "count": count,
        "dividend_type": dividend_type,
        "fill_data": fill_data,
    }
    if data_dir:
        kwargs["data_dir"] = data_dir
    return _run(xtdata.get_local_data, **kwargs)


@mcp.tool()
def get_full_kline(
    field_list: list[str] | None = None,
    stock_list: list[str] | None = None,
    period: str = "1m",
    start_time: str = "",
    end_time: str = "",
    count: int = 1,
    dividend_type: str = "none",
    fill_data: bool = True,
) -> dict[str, Any]:
    """
    获取最新交易日 K 线全推数据。

    输入参数:
        field_list: list[str] | None - 要获取的字段列表，默认为空（返回所有字段）
        stock_list: list[str] | None - 股票代码列表，格式为 '代码.市场'
        period: str - K线周期，默认为 '1m'。支持 1m/5m/15m/30m/1h/1d 等
        start_time: str - 起始时间，格式为 'YYYYMMDD' 或 'YYYYMMDDHHmmSS'
        end_time: str - 结束时间
        count: int - 数据条数，默认为 1（仅取最新交易日数据）
        dividend_type: str - 复权类型，默认为 'none'
        fill_data: bool - 是否填充数据，默认为 True

    输出:
        dict[str, Any] - 返回 { field: pd.DataFrame }，field 为字段名，DataFrame 索引为 stock_list，列为时间列表

    功能说明:
        获取当前交易日的最新 K 线全推数据，适用于实时行情监控场景。
        注意：此接口仅支持获取当前交易日数据，不返回历史数据。
    """
    xtdata = _xtdata()
    return _run(
        xtdata.get_full_kline,
        field_list or [],
        stock_list or [],
        period,
        start_time,
        end_time,
        count,
        dividend_type,
        fill_data,
    )


@mcp.tool()
def download_history_data(
    stock_code: str,
    period: str,
    start_time: str = "",
    end_time: str = "",
    incrementally: bool | None = None,
) -> dict[str, Any]:
    """
    下载单个标的历史行情数据到本地缓存。

    输入参数:
        stock_code: str - 股票代码，格式为 '代码.市场'，如 '600000.SH'
        period: str - K线周期，如 '1d'（日线）、'1m'（1分钟）、'5m'、'tick'（逐笔）等
        start_time: str - 起始时间，格式为 'YYYYMMDD'，如 '20200101'。空字符串表示从最早开始
        end_time: str - 结束时间，格式为 'YYYYMMDD'，空字符串表示到最新
        incrementally: bool | None - 增量下载模式。
            - True：增量下载，仅下载新增数据
            - False：全量下载，忽略 start_time
            - None（默认）：根据 start_time 是否为空自动判断（空则全量，非空则增量）

    输出:
        dict[str, Any] - 无返回值（None）

    功能说明:
        将指定股票的历史行情数据下载到本地缓存。下载完成后可通过 get_market_data 查询。
        对于已下载的数据建议使用增量下载以节省时间和带宽。
    """
    xtdata = _xtdata()
    return _run(
        xtdata.download_history_data,
        stock_code,
        period,
        start_time,
        end_time,
        incrementally,
    )


@mcp.tool()
def download_history_data2(
    stock_list: list[str],
    period: str,
    start_time: str = "",
    end_time: str = "",
    incrementally: bool | None = None,
) -> dict[str, Any]:
    """
    批量下载多个标的历史行情数据。

    输入参数:
        stock_list: list[str] - 股票代码列表，格式为 '代码.市场'，如 ['600000.SH', '000001.SZ']
        period: str - K线周期，如 '1d'、'1m'、'5m'、'tick' 等
        start_time: str - 起始时间，格式为 'YYYYMMDD'。空字符串表示从最早开始
        end_time: str - 结束时间，格式为 'YYYYMMDD'。空字符串表示到最新
        incrementally: bool | None - 增量下载模式，同 download_history_data

    输出:
        dict[str, Any] - 无返回值（None）

    功能说明:
        批量下载多个股票的历史行情数据，是 download_history_data 的批量版本。
        适合在首次全量同步或定期更新行情数据时使用。
    """
    xtdata = _xtdata()
    return _run(
        xtdata.download_history_data2,
        stock_list,
        period,
        start_time,
        end_time,
        None,
        incrementally,
    )


@mcp.tool()
def get_divid_factors(
    stock_code: str,
    start_time: str = "",
    end_time: str = "",
) -> dict[str, Any]:
    """
    获取除权除息因子数据。

    输入参数:
        stock_code: str - 股票代码，格式为 '代码.市场'，如 '600000.SH'
        start_time: str - 起始时间，格式为 'YYYYMMDD'，空字符串表示不限起始
        end_time: str - 结束时间，格式为 'YYYYMMDD'，空字符串表示不限结束

    输出:
        dict[str, Any] - pd.DataFrame，包含以下列：
            - interest：每股分红（利息）
            - stockBonus：每股送股
            - stockGift：每股赠股
            - allotNum：每股配股数量
            - allotPrice：配股价格
            - gugai：股改影响
            - dr：除权标记

    功能说明:
        获取指定股票在时间范围内的除权除息因子数据。
        用于计算前复权/后复权价格，是量化分析中调整股价的重要依据。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_divid_factors, stock_code, start_time, end_time)


@mcp.tool()
def get_period_list() -> dict[str, Any]:
    """
    获取当前连接可用的行情数据周期列表。

    输入参数:
        无

    输出:
        dict[str, Any] - list[str]，返回当前行情服务支持的数据周期。
            常见值：'tick'（逐笔）、'1m'、'5m'、'15m'、'30m'、'1h'、'1d'、'1w'、'1mon'、'1q'、'1hy'、'1y'

    功能说明:
        查询当前 xtdata 连接所支持的 K 线周期类型。
        不同数据源（如 Level-1、Level-2）支持的周期可能不同。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_period_list)


@mcp.tool()
def get_holidays() -> dict[str, Any]:
    """
    获取当前年度的所有节假日日期。

    输入参数:
        无

    输出:
        dict[str, Any] - list[str]，返回 8 位字符串格式的节假日日期列表，如 ['20240101', '20240102', ...]

    功能说明:
        获取当年所有的非交易日（节假日）列表。
        需提前通过 download_holiday_data 下载节假日数据才能获取完整结果。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_holidays)


@mcp.tool()
def get_trading_calendar(
    market: str,
    start_time: str = "",
    end_time: str = "",
) -> dict[str, Any]:
    """
    获取指定市场的交易日历。

    输入参数:
        market: str - 市场代码，如 'SH'（上海）、'SZ'（深圳）
        start_time: str - 起始时间，格式为 'YYYYMMDD'（8位字符串），空字符串表示不限制起始
        end_time: str - 结束时间，格式为 'YYYYMMDD'，空字符串表示不限制结束

    输出:
        dict[str, Any] - 返回交易日期列表，格式为 'YYYYMMDD' 字符串列表

    功能说明:
        获取指定市场在时间范围内的所有交易日列表。
        支持查询未来日期（需已下载节假日数据）。
        可用于量化策略中遍历交易日的逻辑。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_trading_calendar, market, start_time, end_time)


@mcp.tool()
def get_trading_dates(
    market: str,
    start_time: str = "",
    end_time: str = "",
    count: int = -1,
) -> dict[str, Any]:
    """
    获取交易日列表（返回时间戳格式）。

    输入参数:
        market: str - 市场代码，如 'SH'（上海）、'SZ'（深圳）
        start_time: str - 起始时间，格式为 'YYYYMMDD'
        end_time: str - 结束时间，格式为 'YYYYMMDD'
        count: int - 数据条数。>=0 时以 end_time 为基准向前取 count 个交易日；-1 时返回范围内全部

    输出:
        dict[str, Any] - list[datetime/timestamp]，返回交易日时间戳列表

    功能说明:
        获取指定市场在时间范围内的交易日列表，与 get_trading_calendar 的区别在于返回值是时间戳格式。
        适合需要按时间戳进行日期计算的场景。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_trading_dates, market, start_time, end_time, count)


@mcp.tool()
def get_instrument_detail(stock_code: str, iscomplete: bool = False) -> dict[str, Any]:
    """
    获取合约详细基础信息。

    输入参数:
        stock_code: str - 合约代码，格式为 '代码.市场'，如 '600000.SH'
        iscomplete: bool - 是否返回完整字段，默认为 False。
            - False：返回常用字段
            - True：返回所有字段（包括交易费率、保证金率等）

    输出:
        dict[str, Any] - 合约信息字典，完整字段包括：
            - ExchangeID：交易所代码（如 'SH'、'SZ'）
            - InstrumentID：合约代码
            - InstrumentName：合约名称
            - ProductID：产品代码
            - PreClose：前收盘价
            - UpStopPrice：涨停价
            - DownStopPrice：跌停价
            - FloatVolume：流通股本
            - TotalVolume：总股本
            - LongMarginRatio：多头保证金率
            - ShortMarginRatio：空头保证金率
            - PriceTick：价格最小变动单位
            - VolumeMultiple：合约乘数
            - MainContract：是否主合约
            - InstrumentStatus：合约状态
            - IsTrading：是否在交易
            - （isonplete=True 时额外返回）ChargeType、ChargeOpen、ChargeClose、OptionType 等

    功能说明:
        获取指定合约的详细基础信息，包括交易相关参数和合约状态。
        是量化交易中了解合约属性的重要接口。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_instrument_detail, stock_code, iscomplete)


@mcp.tool()
def get_instrument_type(stock_code: str) -> dict[str, Any]:
    """
    获取合约类型。

    输入参数:
        stock_code: str - 合约代码，格式为 '代码.市场'，如 '600000.SH'

    输出:
        dict[str, Any] - dict[str, bool]，key 为合约类型，value 为是否为该类型。
            可能的类型包括：
            - 'index'：是否为指数
            - 'stock'：是否为股票
            - 'fund'：是否为基金
            - 'etf'：是否为ETF

    功能说明:
        判断指定合约的类型，可同时返回多种类型标签（如股票型ETF）。
        适合在处理混合标的后需要分类处理的场景。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_instrument_type, stock_code)


@mcp.tool()
def get_sector_list() -> dict[str, Any]:
    """
    获取所有可用的板块（行业/概念分类）列表。

    输入参数:
        无

    输出:
        dict[str, Any] - list[str]，返回所有板块名称列表，如 ['银行'、'房地产'、'医疗器械'、'新能源汽车' ...]

    功能说明:
        获取当前行情数据支持的所有板块分类名称。
        需先调用 download_sector_data 下载板块数据才能获取完整列表。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_sector_list)


@mcp.tool()
def get_stock_list_in_sector(sector_name: str, real_timetag: int = 0) -> dict[str, Any]:
    """
    获取指定板块内的所有成分股列表。

    输入参数:
        sector_name: str - 板块名称，需为 get_sector_list 中存在的名称
        real_timetag: int - 是否返回实时成分，默认为 0。
            - 0：返回当前板块成分（可能会有成分股调整）
            - 非0：返回历史上某一时刻的成分（需配合时间戳使用）

    输出:
        dict[str, Any] - list[str]，返回成分股代码列表，格式为 '代码.市场'，如 ['600000.SH', '600001.SH', ...]

    功能说明:
        获取指定板块（如行业板块、概念板块）包含的所有股票代码。
        支持查询历史成分（需指定 real_timetag）。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_stock_list_in_sector, sector_name, real_timetag)


@mcp.tool()
def get_index_weight(index_code: str) -> dict[str, Any]:
    """
    获取指数成分股及其权重信息。

    输入参数:
        index_code: str - 指数代码，格式为 '代码.市场'，如 '000001.SH'（上证指数）、'399001.SZ'（深证成指）

    输出:
        dict[str, Any] - dict[str, float]，key 为成分股代码，value 为该成分股在指数中的权重（百分比）。
            示例：{ '600000.SH': 2.35, '600001.SH': 0.85, ... }

    功能说明:
        获取指定指数的成分股及其对应的权重信息。
        用于指数增强策略、ETF 套利分析、风险平价等量化场景。
        需先调用 download_index_weight 下载指数权重数据。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_index_weight, index_code)


@mcp.tool()
def download_index_weight() -> dict[str, Any]:
    """
    下载指数成分权重信息到本地。

    输入参数:
        无

    输出:
        dict[str, Any] - 无返回值（None）

    功能说明:
        下载所有主要指数的成分股权重数据到本地缓存。
        下载完成后可通过 get_index_weight 查询各指数成分权重。
    """
    xtdata = _xtdata()
    return _run(xtdata.download_index_weight)


@mcp.tool()
def get_financial_data(
    stock_list: list[str],
    table_list: list[str] | None = None,
    start_time: str = "",
    end_time: str = "",
    report_type: str = "report_time",
) -> dict[str, Any]:
    """
    获取财务数据。

    输入参数:
        stock_list: list[str] - 股票代码列表，格式为 '代码.市场'，如 ['600000.SH']
        table_list: list[str] | None - 财务表格类型列表，默认为空（返回所有表格）。
            可选值：
            - 'Balance'：资产负债表
            - 'Income'：利润表
            - 'CashFlow'：现金流量表
            - 'Capital'：资本变动表
            - 'Holdernum'：股东人数
            - 'Top10holder'：前十大股东
            - 'Top10flowholder'：前十大流通股东
            - 'Pershareindex'：每股指标
        start_time: str - 起始时间，格式为 'YYYYMMDD'，空字符串表示不限
        end_time: str - 结束时间，格式为 'YYYYMMDD'，空字符串表示不限
        report_type: str - 报告时间类型，默认为 'report_time'。
            - 'report_time'：按报告期（财务报表的会计期间）
            - 'announce_time'：按公告期（财务报表实际披露时间）

    输出:
        dict[str, Any] - dict[stock: dict[table: DataFrame]]。
            外层 key 为股票代码，内层 key 为表格类型，value 为 pd.DataFrame

    功能说明:
        获取指定股票的财务数据，包括资产负债表、利润表、现金流量表等。
        支持按报告期和公告期两种维度查询，适合基本面分析和财务筛选。
    """
    xtdata = _xtdata()
    return _run(
        xtdata.get_financial_data,
        stock_list,
        table_list or [],
        start_time,
        end_time,
        report_type,
    )


@mcp.tool()
def get_cb_info(stockcode: str) -> dict[str, Any]:
    """
    获取可转债（Convertible Bond）基础信息。

    输入参数:
        stockcode: str - 可转债代码，格式为 '代码.市场'，如 '113009.SH'

    输出:
        dict[str, Any] - 可转债详细信息字典，包含转股价、到期日、赎回条款等字段

    功能说明:
        获取指定可转债的详细基础信息，包括正股代码、转股价、到期时间、赎回/回售条款等。
        需先调用 download_cb_data 下载可转债数据。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_cb_info, stockcode)


@mcp.tool()
def get_ipo_info(start_time: str = "", end_time: str = "") -> dict[str, Any]:
    """
    获取新股申购信息。

    输入参数:
        start_time: str - 起始时间，格式为 'YYYYMMDD'，空字符串表示不限起始
        end_time: str - 结束时间，格式为 'YYYYMMDD'，空字符串表示不限结束

    输出:
        dict[str, Any] - list[dict]，每只新股一条记录，包含字段：
            - securityCode：证券代码
            - codeName：证券名称
            - market：市场代码
            - actIssueQty：实际发行数量
            - onlineIssueQty：网上发行数量
            - onlineSubCode：网上申购代码
            - onlineSubMaxQty：网上申购上限
            - publishPrice：发行价
            - isProfit：是否盈利
            - industryPe：行业市盈率
            - afterPE：上市后市盈率

    功能说明:
        获取指定时间范围内的新股申购信息，包括发行价、申购代码、发行数量等。
        适合打新策略分析和打新日历构建。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_ipo_info, start_time, end_time)


@mcp.tool()
def get_etf_info() -> dict[str, Any]:
    """
    获取所有 ETF 申赎清单信息。

    输入参数:
        无

    输出:
        dict[str, Any] - dict，key 为 ETF 代码，value 为该 ETF 的申赎清单信息（成分股及权重等）

    功能说明:
        获取全市场 ETF 的申购赎回清单（PCF）信息。
        用于 ETF 套利、ETF 期现套利等量化策略。
    """
    xtdata = _xtdata()
    return _run(xtdata.get_etf_info)


def get_app() -> Any:
    """获取 ASGI 应用，供 uvicorn 等服务器使用。"""
    return mcp.http_app(transport="sse")


def main() -> None:
    import os
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    main()

