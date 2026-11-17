import type { Schemas } from "../../api/client";

/** Nhãn trục thời gian từ ngày đầu mốc (YYYY-MM-DD): 16/11, 11/2026, Q4/2026, 2026. */
export function periodLabel(start: string, period: Schemas["SeriesPeriod"]): string {
  const [year, month, day] = start.split("-");
  switch (period) {
    case "DAY":
      return `${day}/${month}`;
    case "MONTH":
      return `${month}/${year}`;
    case "QUARTER":
      return `Q${Math.ceil(Number(month) / 3)}/${year}`;
    case "YEAR":
      return year;
  }
}
