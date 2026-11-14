// 3.5 Ca thu ngân: thu ngân mở ca, đóng ca với tiền kiểm đếm, xem kết quả đối soát ca của mình.
// QL xem ca chi nhánh, xác nhận chốt ca thu ngân tự đóng, đóng ca thay kèm người làm chứng (CA-03, CA-04);
// HQ xem mọi chi nhánh, xác nhận chốt ca QL đóng thay, duyệt thay ca thu ngân tự đóng kèm lý do (quyết định 14). QL, HQ duyệt hoàn tiền mặt cho giao dịch
// hoàn điện tử thất bại (TH-04). Tiền mặt kỳ vọng, chênh lệch, tổng theo phương thức lấy từ API (dẫn xuất).
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
} from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime, money } from "../../format";
import {
  SHIFT_STATUS_LABEL,
  TXN_METHOD_LABEL,
  TXN_STATUS_LABEL,
  TXN_TYPE_LABEL,
  optionsOf,
} from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";
import { ReconcileModal } from "../payments/PendingTransactions";
import { canApproveCashRefund, canReconcile, shiftActions } from "./shiftActions";

type Shift = Schemas["Shift"];
type ShiftDetail = Schemas["ShiftDetail"];
type Txn = Schemas["Transaction"];

/** Ca đang mở của thu ngân (null: chưa mở ca). Khóa "shifts" để mọi thao tác ghi tải lại cùng lúc. */
export const useCurrentShift = (enabled = true) =>
  useQuery({
    queryKey: ["shifts", "current"],
    queryFn: () => unwrap(client.GET("/shifts/current")),
    enabled,
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

/** Giao dịch thất bại; QL, HQ duyệt hoàn tiền mặt cho giao dịch hoàn điện tử thất bại (TH-04). */
function FailedTransactions({ rows }: { rows: Txn[] }) {
  const role = useAuth().user?.role;
  const [approving, setApproving] = useState<Txn | null>(null);
  const approve = useWrite(
    (body: Schemas["CashRefundApproval"]) =>
      unwrap(
        client.POST("/transactions/{txn_id}/approve-cash-refund", {
          params: { path: { txn_id: approving!.txn_id } },
          body,
        }),
      ),
    ["shifts", "returns"],
  );
  return (
    <>
      <Table<Txn>
        rowKey="txn_id"
        size="small"
        pagination={false}
        dataSource={rows}
        scroll={{ x: true }}
        columns={[
          ...txnColumns,
          {
            title: "Hoàn tiền mặt",
            render: (_, txn) =>
              txn.cash_refund_approved_by
                ? `${txn.cash_refund_approved_by} đã duyệt: ${txn.cash_refund_reason}`
                : role &&
                  canApproveCashRefund(txn, role) && (
                    <Button size="small" onClick={() => setApproving(txn)}>
                      Duyệt hoàn tiền mặt
                    </Button>
                  ),
          },
        ]}
      />
      {approving && (
        <FormModal<Schemas["CashRefundApproval"]>
          title={`Duyệt hoàn tiền mặt cho giao dịch ${approving.txn_id}`}
          onClose={() => setApproving(null)}
          onSubmit={approve.mutateAsync}
        >
          <p>
            Phiếu trả {approving.return_id}, số tiền {money(approving.amount)}. Lần hoàn kế tiếp của thu
            ngân sẽ là tiền mặt.
          </p>
          <Form.Item label="Lý do" name="reason" rules={[{ required: true, whitespace: true }]}>
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}
    </>
  );
}

/** Giao dịch Chờ kết quả của ca; ca đã đóng thì thu ngân tra soát tại đây để ca chốt được (CA-03). */
function PendingInShift({ shift }: { shift: ShiftDetail }) {
  const role = useAuth().user?.role;
  const [reconciling, setReconciling] = useState<Txn | null>(null);
  return (
    <>
      <Table<Txn>
        rowKey="txn_id"
        size="small"
        pagination={false}
        dataSource={shift.pending}
        scroll={{ x: true }}
        columns={[
          ...txnColumns,
          {
            title: "Thao tác",
            render: (_, txn) =>
              role &&
              canReconcile(shift, txn, role) && (
                <Button size="small" onClick={() => setReconciling(txn)}>
                  Tra soát
                </Button>
              ),
          },
        ]}
      />
      {reconciling && <ReconcileModal txn={reconciling} onClose={() => setReconciling(null)} />}
    </>
  );
}

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
        {shift.proxy_closed_by && (
          <Descriptions.Item label="Đóng thay">
            {shift.proxy_closed_by}, làm chứng {shift.witness_id}: {shift.proxy_reason}
          </Descriptions.Item>
        )}
        {shift.settled_at && (
          <Descriptions.Item label="Xác nhận">
            {dateTime(shift.settled_at)} bởi {shift.confirmed_by}
            {shift.confirm_reason && `: ${shift.confirm_reason}`}
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
      <PendingInShift shift={shift} />
      <h4>Giao dịch thất bại</h4>
      <FailedTransactions rows={shift.failed} />
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
  const role = useAuth().user?.role;
  const isCashier = role === "CASHIER";
  // GET /shifts/current chỉ dành cho thu ngân
  const current = useCurrentShift(isCashier);
  const [status, setStatus] = useState<Shift["status"]>();
  const history = useQuery({
    queryKey: ["shifts", "list", status],
    queryFn: () => unwrap(client.GET("/shifts", { params: { query: { status } } })),
  });
  const [dialog, setDialog] = useState<"open" | "close" | null>(null);
  const [proxyClosing, setProxyClosing] = useState<Shift | null>(null);
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
  const [hqConfirming, setHqConfirming] = useState<Shift | null>(null);
  const confirm = useWrite(
    ({ shiftId, body }: { shiftId: string; body?: Schemas["ShiftConfirm"] }) =>
      unwrap(
        client.POST("/shifts/{shift_id}/confirm", { params: { path: { shift_id: shiftId } }, body }),
      ),
    ["shifts", "reports"],
  );
  const proxyClose = useWrite(
    (body: Schemas["ShiftProxyClose"]) =>
      unwrap(
        client.POST("/shifts/{shift_id}/proxy-close", {
          params: { path: { shift_id: proxyClosing!.shift_id } },
          body,
        }),
      ),
    ["shifts"],
  );

  // Nút xác nhận chốt, đóng ca thay theo vai trò (CA-03, CA-04); API kiểm tra lại
  const actionColumn = {
    title: "Thao tác",
    render: (_: unknown, row: Shift) =>
      role &&
      shiftActions(row, role).map((action) =>
        action === "confirm" && role === "HQ" && !row.proxy_closed_by ? (
          <Button key={action} size="small" type="primary" onClick={() => setHqConfirming(row)}>
            Duyệt thay chốt ca
          </Button>
        ) : action === "confirm" ? (
          <Popconfirm
            key={action}
            title={`Xác nhận chốt ca ${row.shift_id}?`}
            description={
              row.proxy_closed_by
                ? `Duyệt thay ca QL đóng thay. Lý do: ${row.proxy_reason}`
                : "Đã nhận tiền và kiểm tra kết quả đối soát"
            }
            onConfirm={() => confirm.mutate({ shiftId: row.shift_id })}
          >
            <Button size="small" type="primary">
              Xác nhận chốt
            </Button>
          </Popconfirm>
        ) : (
          <Button key={action} size="small" danger onClick={() => setProxyClosing(row)}>
            Đóng ca thay
          </Button>
        ),
      ),
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {isCashier && (
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
      )}

      <Card
        title={isCashier ? "Ca của tôi" : role === "HQ" ? "Ca các chi nhánh" : "Ca của chi nhánh"}
        extra={
          !isCashier && (
            <Select
              allowClear
              placeholder="Mọi trạng thái"
              style={{ minWidth: 160 }}
              options={optionsOf(SHIFT_STATUS_LABEL)}
              value={status}
              onChange={setStatus}
            />
          )
        }
      >
        <Table<Shift>
          rowKey="shift_id"
          loading={history.isPending}
          dataSource={history.data}
          scroll={{ x: true }}
          expandable={{ expandedRowRender: (row) => <ShiftHistoryDetail shiftId={row.shift_id} /> }}
          columns={[
            { title: "Mã ca", dataIndex: "shift_id" },
            ...(isCashier
              ? []
              : [
                  { title: "Chi nhánh", dataIndex: "branch_id" },
                  { title: "Thu ngân", dataIndex: "cashier_id" },
                ]),
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
            ...(isCashier
              ? []
              : [
                  {
                    title: "Đóng thay",
                    dataIndex: "proxy_closed_by",
                    render: (by: string | null) => by ?? "",
                  },
                  actionColumn,
                ]),
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

      {hqConfirming && (
        <FormModal<Schemas["ShiftConfirm"]>
          title={`Duyệt thay xác nhận chốt ca ${hqConfirming.shift_id}`}
          onClose={() => setHqConfirming(null)}
          onSubmit={(body) => confirm.mutateAsync({ shiftId: hqConfirming.shift_id, body })}
        >
          <p>Chỉ dùng khi QL chi nhánh vắng mặt (ma trận 2.2).</p>
          <Form.Item
            label="Lý do duyệt thay"
            name="confirm_reason"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}

      {proxyClosing && (
        <FormModal<Schemas["ShiftProxyClose"]>
          title={`Đóng ca thay ${proxyClosing.shift_id} (thu ngân ${proxyClosing.cashier_id})`}
          onClose={() => setProxyClosing(null)}
          onSubmit={proxyClose.mutateAsync}
        >
          <Form.Item label="Tiền mặt kiểm đếm" name="counted_cash" rules={[{ required: true }]}>
            <InputNumber min={0} precision={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="Lý do chênh lệch (bắt buộc nếu có chênh lệch)" name="variance_reason">
            <Input.TextArea />
          </Form.Item>
          {/* QL không xem được danh sách nhân viên (ma trận 2.2): nhập mã, API kiểm tra CA-04 */}
          <Form.Item
            label="Mã nhân viên làm chứng"
            name="witness_id"
            extra="Nhân viên Đang làm cùng chi nhánh, khác bạn và khác thu ngân của ca"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="Lý do đóng thay"
            name="proxy_reason"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}
    </Space>
  );
}
