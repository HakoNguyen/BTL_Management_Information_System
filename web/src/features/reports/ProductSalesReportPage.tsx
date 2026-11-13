// 5.2 Sản phẩm bán: xếp hạng, theo nhóm, hàng chậm bán (DT-05).
import { useQuery } from "@tanstack/react-query";
import { Card, Form, Select, Table, Typography } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { RANK_BY_LABEL, optionsOf } from "../../labels";
import { moneyColumn } from "../../ui";
import { ReportFilter, ReportHeader, type ReportParams } from "./ReportFilter";

type Params = ReportParams & { rank_by: Schemas["RankBy"] };

export function ProductSalesReportPage() {
  const [params, setParams] = useState<Params | null>(null);
  const report = useQuery({
    queryKey: ["reports", "products", params],
    queryFn: () => unwrap(client.GET("/reports/products", { params: { query: params! } })),
    enabled: params !== null,
  });
  const data = report.data;

  return (
    <Card title="Báo cáo sản phẩm bán">
      <ReportFilter<Params> onSubmit={setParams} initialValues={{ rank_by: "QUANTITY" }}>
        <Form.Item label="Xếp hạng" name="rank_by">
          <Select style={{ minWidth: 150 }} options={optionsOf(RANK_BY_LABEL)} />
        </Form.Item>
      </ReportFilter>
      <ReportHeader report={data} error={report.error} />
      {data && (
        <>
          <Typography.Title level={5}>Sản phẩm ({RANK_BY_LABEL[data.rank_by]})</Typography.Title>
          <Table<Schemas["ProductSalesLine"]>
            rowKey="product_id"
            dataSource={data.products}
            scroll={{ x: true }}
            columns={[
              { title: "Hạng", dataIndex: "rank", align: "right" },
              {
                title: "Hạng kỳ trước",
                dataIndex: "previous_rank",
                align: "right",
                render: (rank: number | null) => rank ?? "—",
              },
              { title: "Mã", dataIndex: "product_id" },
              { title: "Tên", dataIndex: "name" },
              { title: "Nhóm", dataIndex: "group_id" },
              { title: "SL bán", dataIndex: "sold_qty", align: "right" },
              { title: "SL trả", dataIndex: "returned_qty", align: "right" },
              { title: "SL thuần", dataIndex: "net_qty", align: "right" },
              moneyColumn("Giá trị thuần", "net_value"),
            ]}
          />
          <Typography.Title level={5}>Theo nhóm</Typography.Title>
          <Table<Schemas["GroupSalesLine"]>
            rowKey="group_id"
            dataSource={data.groups}
            pagination={false}
            columns={[
              { title: "Mã nhóm", dataIndex: "group_id" },
              { title: "Tên nhóm", dataIndex: "name" },
              { title: "SL bán", dataIndex: "sold_qty", align: "right" },
              { title: "SL trả", dataIndex: "returned_qty", align: "right" },
              { title: "SL thuần", dataIndex: "net_qty", align: "right" },
              moneyColumn("Giá trị thuần", "net_value"),
            ]}
          />
          <Typography.Title level={5}>Hàng chậm bán (còn tồn, không bán được trong kỳ)</Typography.Title>
          <Table<Schemas["SlowMovingLine"]>
            rowKey={(line) => `${line.branch_id}-${line.product_id}`}
            dataSource={data.slow_moving}
            columns={[
              { title: "Chi nhánh", dataIndex: "branch_id" },
              { title: "Mã", dataIndex: "product_id" },
              { title: "Tên", dataIndex: "name" },
              { title: "Tồn", dataIndex: "quantity", align: "right" },
            ]}
          />
        </>
      )}
    </Card>
  );
}
