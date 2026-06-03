-- 012 initial schema: market-data warehouse.
CREATE TABLE IF NOT EXISTS md_bars (
    broker_id      text             NOT NULL,
    code           text             NOT NULL,
    period         text             NOT NULL,
    dividend_type  text             NOT NULL DEFAULT 'none',
    dt             text             NOT NULL,
    open           double precision,
    high           double precision,
    low            double precision,
    close          double precision,
    volume         double precision,
    amount         double precision,
    updated_at     timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (broker_id, code, period, dividend_type, dt)
);
