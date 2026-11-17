// Biểu đồ thanh ngang dùng chung cho các trang báo cáo. Chỉ vẽ số liệu API trả về, không tự tính.
import { Card, Empty } from "antd";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BRAND, NAVY } from "../../ui";

/** Màu cột: bán (xanh), trả hoặc hoàn (đỏ cam, tiêu cực), thuần (xanh đậm). */
export const CHART_COLOR = { gross: BRAND, returns: "#fa541c", net: NAVY };

export type Series<T> = { key: keyof T & string; name: string; color: string };

type Props<T> = {
  title: string;
  data: T[];
  /** Trường làm nhãn của mỗi thanh. */
  label: keyof T & string;
  series: Series<T>[];
  /** Số tiền thì hiện dạng 1.250.000, trục rút gọn 1,3 Tr; số lượng thì giữ nguyên. */
  money?: boolean;
};

const full = (value: number) => value.toLocaleString("vi-VN");
const compact = (value: number) =>
  new Intl.NumberFormat("vi-VN", { notation: "compact", maximumFractionDigits: 1 }).format(value);

export function BarChartCard<T extends object>({ title, data, label, series, money }: Props<T>) {
  // Cao theo số dòng và số cột trong mỗi dòng, cộng chỗ cho trục và chú thích
  const height = Math.max(160, data.length * (16 + series.length * 12) + 70);

  return (
    <Card size="small" title={title} style={{ height: "100%" }}>
      {data.length === 0 ? (
        <Empty description="Không có số liệu trong kỳ" />
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
            <CartesianGrid horizontal={false} strokeDasharray="3 3" />
            <XAxis type="number" tickFormatter={money ? compact : full} />
            <YAxis type="category" dataKey={label} width={130} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value: number) => (money ? `${full(value)} ₫` : full(value))} />
            {series.length > 1 && <Legend />}
            {series.map((s) => (
              <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[0, 4, 4, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
