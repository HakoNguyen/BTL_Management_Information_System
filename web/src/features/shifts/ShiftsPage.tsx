// 3.5 Ca thu ngân: mở ca, đóng ca với tiền kiểm đếm, xem kết quả đối soát ca của mình.
// CA-01, CA-02 do API kiểm tra; tiền mặt kỳ vọng, chênh lệch, tổng theo phương thức lấy từ API (dẫn xuất).
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Descriptions, Form, Input, InputNumber, Space, Table, Tag } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime, money } from "../../format";
import { SHIFT_STATUS_LABEL, TXN_METHOD_LABEL, TXN_STATUS_LABEL, TXN_TYPE_LABEL } from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";

type Shift = Schemas["Shift"];
type ShiftDetail = Schemas["ShiftDetail"];

/** Ca đang mở của thu ngân (null: chưa mở ca). Khóa "shifts" để mọi thao tác ghi tải lại cùng lúc. */
export const useCurrentShift = () =>
  useQuery({
    queryKey: ["shifts", "current"],
    queryFn: () => unwrap(client.GET("/shifts/current")),
  });

/** Cột giao dịch dùng chung cho kết quả ca và danh sách chờ kết quả. */
export const txnColumns = [
  { title: "Mã GD", dataIndex: "txn_id" },
  { title: "Loại", dataIndex: "type", render: (v: Schemas["TxnType"]) => TXN_TYPE_LABEL[v] },
  { title: "Đơn", dataIndex: "order_id" },
  { title: "Phiếu trả", dataIndex: "return_id" },
  { title: "Phương thức", dataIndex: "method", render: (v: Schemas["TxnMethod"]) => TXN_METHOD_LABEL[v] },
  moneyColumn("Số tiền", "amount"),
  { title: "Tạo lúc", dataIndex: "created_at", render: dateTime },
  {
    title: "Trạng thái",
    dataIndex: "status",
    render: (v: Schemas["TxnStatus"]) => <Tag>{TXN_STATUS_LABEL[v]}</Tag>,
  },
];

const txnTable = (rows: Schemas["Transaction"][]) => (
  <Table rowKey="txn_id" size="small" pagination={false} dataSource={rows} columns={txnColumns} />
);

/** Kết quả đối soát của một ca (CA-03), số liệu nguyên từ API. */
function ShiftResult({ shift }: { shift: ShiftDetail }) {
  return (
    <>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
        <Descriptions.Item label="Mã ca">{shift.shift_id}</Descriptions.Item>
        <Descriptions.Item label="Trạng thái">{SHIFT_STATUS_LABEL[shift.status]}</Descriptions.Item>
        <Descriptions.Item label="Mở lúc">{dateTime(shift.opened_at)}</Descriptions.Item>
        <Descriptions.Item label="Đóng lúc">{dateTime(shift.closed_at)}</Descriptions.Item>
        <Descriptions.Item label="Tiền đầu ca">{money(shift.opening_cash)}</Descriptions.Item>
        <Descriptions.Item label="Thu tiền mặt">{money(shift.cash_collected)}</Descriptions.Item>
        <Descriptions.Item label="Hoàn tiền mặt">{money(shift.cash_refunded)}</Descriptions.Item>
        <Descriptions.Item label="Tiền mặt kỳ vọng">{money(shift.expected_cash)}</Descriptions.Item>
        <Descriptions.Item label="Tiền kiểm đếm">
          {shift.counted_cash === null ? "Chưa kiểm đếm" : money(shift.counted_cash)}
        </Descriptions.Item>
        <Descriptions.Item label="Chênh lệch">
          {shift.variance === null ? "Chưa kiểm đếm" : money(shift.variance)}
        </Descriptions.Item>
        {shift.variance_reason && (
          <Descriptions.Item label="Lý do chênh lệch">{shift.variance_reason}</Descriptions.Item>
        )}
        {shift.settled_at && (
          <Descriptions.Item label="Xác nhận">
            {dateTime(shift.settled_at)} bởi {shift.confirmed_by}
          </Descriptions.Item>
        )}
      </Descriptions>
      <h4>Giao dịch điện tử thành công</h4>
      <Table<Schemas["ShiftMethodTotal"]>
        rowKey={(row) => `${row.type}-${row.method}`}
        size="small"
        pagination={false}
        dataSource={shift.electronic}
        columns={[
          { title: "Loại", dataIndex: "type", render: (v: Schemas["TxnType"]) => TXN_TYPE_LABEL[v] },
          {
            title: "Phương thức",
            dataIndex: "method",
            render: (v: Schemas["TxnMethod"]) => TXN_METHOD_LABEL[v],
          },
          { title: "Số giao dịch", dataIndex: "count", align: "right" },
          moneyColumn("Số tiền", "amount"),
        ]}
      />
      <h4>Giao dịch chờ kết quả</h4>
      {txnTable(shift.pending)}
      <h4>Giao dịch thất bại</h4>
      {txnTable(shift.failed)}
    </>
  );
}

/** Dòng mở rộng của lịch sử ca: tải kết quả đối soát khi mở. */
function ShiftHistoryDetail({ shiftId }: { shiftId: string }) {
  const detail = useQuery({
    queryKey: ["shifts", "detail", shiftId],
    queryFn: () =>
      unwrap(client.GET("/shifts/{shift_id}", { params: { path: { shift_id: shiftId } } })),
  });
  return detail.data ? <ShiftResult shift={detail.data} /> : null;
}

export function ShiftsPage() {
  const current = useCurrentShift();
  const history = useQuery({
    queryKey: ["shifts", "list"],
    queryFn: () => unwrap(client.GET("/shifts", { params: { query: {} } })),
  });
  const [dialog, setDialog] = useState<"open" | "close" | null>(null);
  const shift = current.data;

  const open = useWrite(
    (body: Schemas["ShiftOpen"]) => unwrap(client.POST("/shifts", { body })),
    ["shifts"],
  );
  const close = useWrite(
    (body: Schemas["ShiftClose"]) =>
      unwrap(
        client.POST("/shifts/{shift_id}/close", {
          params: { path: { shift_id: shift!.shift_id } },
          body,
        }),
      ),
    ["shifts"],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card
        title="Ca hiện tại"
        loading={current.isPending}
        extra={
          shift ? (
            <Button type="primary" onClick={() => setDialog("close")}>
              Đóng ca
            </Button>
          ) : (
            <Button type="primary" onClick={() => setDialog("open")}>
              Mở ca
            </Button>
          )
        }
      >
        {shift ? <ShiftResult shift={shift} /> : <Alert type="info" message="Chưa có ca đang mở" />}
      </Card>

      <Card title="Ca của tôi">
        <Table<Shift>
          rowKey="shift_id"
          loading={history.isPending}
          dataSource={history.data}
          scroll={{ x: true }}
          expandable={{ expandedRowRender: (row) => <ShiftHistoryDetail shiftId={row.shift_id} /> }}
          columns={[
            { title: "Mã ca", dataIndex: "shift_id" },
            { title: "Mở lúc", dataIndex: "opened_at", render: dateTime },
            { title: "Đóng lúc", dataIndex: "closed_at", render: dateTime },
            {
              title: "Trạng thái",
              dataIndex: "status",
              render: (v: Shift["status"]) => <Tag>{SHIFT_STATUS_LABEL[v]}</Tag>,
            },
            moneyColumn("Tiền mặt kỳ vọng", "expected_cash"),
            {
              ...moneyColumn("Chênh lệch", "variance"),
              render: (v: number | null) => (v === null ? "Chưa kiểm đếm" : money(v)),
            },
          ]}
        />
      </Card>

      {dialog === "open" && (
        <FormModal<Schemas["ShiftOpen"]>
          title="Mở ca"
          onClose={() => setDialog(null)}
          onSubmit={open.mutateAsync}
        >
          <Form.Item label="Tiền đầu ca" name="opening_cash" rules={[{ required: true }]}>
            <InputNumber min={0} precision={0} style={{ width: "100%" }} />
          </Form.Item>
        </FormModal>
      )}

      {dialog === "close" && shift && (
        <FormModal<Schemas["ShiftClose"]>
          title={`Đóng ca ${shift.shift_id}`}
          onClose={() => setDialog(null)}
          onSubmit={close.mutateAsync}
        >
          <Form.Item label="Tiền mặt kiểm đếm" name="counted_cash" rules={[{ required: true }]}>
            <InputNumber min={0} precision={0} style={{ width: "100%" }} />
          </Form.Item>
          {/* Chênh lệch do API tính; thiếu lý do khi chênh lệch khác 0 thì API báo lỗi CA-02 */}
          <Form.Item label="Lý do chênh lệch (bắt buộc nếu có chênh lệch)" name="variance_reason">
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}
    </Space>
  );
}
