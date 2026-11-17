// Doanh thu theo thời gian (tính năng thêm, docs/api.md nhóm 5): gộp, hàng trả, thuần theo ngày/tháng/quý/năm,
// lọc nhóm sản phẩm. Kỳ và chi nhánh lấy theo bộ lọc chung của trang Doanh thu. Số liệu do API tính.
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Empty, Segmented, Select, Space } from "antd";
import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { client, unwrap, type Schemas } from "../../api/client";
import { SERIES_PERIOD_LABEL, optionsOf } from "../../labels";
import { CHART_COLOR } from "./BarChartCard";
import { periodLabel } from "./periodLabel";
import type { ReportParams } from "./ReportFilter";

type Period = Schemas["SeriesPeriod"];

const money = (value: number) => `${value.toLocaleString("vi-VN")} ₫`;
const compact = (value: number) =>
  new Intl.NumberFormat("vi-VN", { notation: "compact", maximumFractionDigits: 1 }).format(value);

export function RevenueTrendCard({ params }: { params: ReportParams }) {
  const [period, setPeriod] = useState<Period>("DAY");
  const [groupId, setGroupId] = useState<string>();
  const groups = useQuery({
    queryKey: ["product-groups"],
    queryFn: () => unwrap(client.GET("/product-groups")),
  });
  const series = useQuery({
    queryKey: ["reports", "revenue-series", params, period, groupId],
    queryFn: () =>
      unwrap(
        client.GET("/reports/revenue/series", {
          params: { query: { ...params, period, group_id: groupId } },
        }),
      ),
  });
  const points = (series.data?.points ?? []).map((p) => ({
    ...p,
    label: periodLabel(p.period_start, period),
  }));
  const empty = points.every((p) => p.gross_revenue === 0 && p.returns_value === 0);

  return (
    <Card
      size="small"
      title="Doanh thu theo thời gian"
      extra={
        <Space wrap>
          <Segmented<Period> value={period} onChange={setPeriod} options={optionsOf(SERIES_PERIOD_LABEL)} />
          <Select
            allowClear
            placeholder="Mọi nhóm sản phẩm"
            style={{ minWidth: 180 }}
            value={groupId}
            onChange={setGroupId}
            options={(groups.data ?? []).map((g) => ({ value: g.group_id, label: g.name }))}
          />
        </Space>
      }
    >
      {groupId && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="Đang lọc theo nhóm: doanh thu là tổng các dòng hàng thuộc nhóm (theo nhóm hiện tại của sản phẩm), số đơn là đơn có hàng của nhóm."
        />
      )}
      {series.error ? (
        <Alert type="error" showIcon message={series.error.message} />
      ) : empty && !series.isPending ? (
        <Empty description="Không có số liệu trong kỳ" />
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={points} margin={{ left: 8, right: 24, top: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={compact} width={70} />
            <Tooltip formatter={(value: number) => money(value)} />
            <Legend />
            <Bar dataKey="gross_revenue" name="Doanh thu gộp" fill={CHART_COLOR.gross} radius={[4, 4, 0, 0]} />
            <Bar dataKey="returns_value" name="Hàng trả" fill={CHART_COLOR.returns} radius={[4, 4, 0, 0]} />
            <Line
              dataKey="net_revenue"
              name="Doanh thu thuần"
              stroke={CHART_COLOR.net}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
