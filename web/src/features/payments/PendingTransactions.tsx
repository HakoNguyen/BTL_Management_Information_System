// Giao dịch Chờ kết quả trong ca đang mở (TT-02): tiền mặt thì xác nhận đã nhận/đã chi,
// điện tử thì nhập kết quả tra soát kèm mã tham chiếu. Dùng cho thu tiền (3.2) và hoàn tiền (3.4).
import { Alert, Button, Form, Input, Popconfirm, Select, Space, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { txnColumns, useCurrentShift } from "../shifts/ShiftsPage";
import { TXN_STATUS_LABEL } from "../../labels";
import { FormModal, useWrite } from "../../ui";

type Txn = Schemas["Transaction"];

// Kết quả giao dịch đổi ca, đơn, phiếu trả, hóa đơn
export const TXN_KEYS = ["shifts", "orders", "returns"];

const RESULTS = ["SUCCESS", "FAILED"] as const;
const txnPath = (id: string) => ({ params: { path: { txn_id: id } } });

export function PendingTransactions({ type }: { type: Schemas["TxnType"] }) {
  const current = useCurrentShift();
  const [reconciling, setReconciling] = useState<Txn | null>(null);
  const confirmCash = useWrite(
    ({ txn, result }: { txn: Txn; result: Schemas["CashConfirm"]["result"] }) =>
      unwrap(
        client.POST("/transactions/{txn_id}/confirm-cash", { ...txnPath(txn.txn_id), body: { result } }),
      ),
    TXN_KEYS,
  );
  const reconcile = useWrite(
    (body: Schemas["Reconcile"]) =>
      unwrap(
        client.POST("/transactions/{txn_id}/reconcile", { ...txnPath(reconciling!.txn_id), body }),
      ),
    TXN_KEYS,
  );

  if (current.isPending) return null;
  if (!current.data)
    return <Alert type="warning" showIcon message="Chưa có ca đang mở: mở ca ở trang Ca thu ngân" />;

  const done = type === "COLLECT" ? "Đã nhận đủ tiền" : "Đã chi đủ tiền";
  const notDone = type === "COLLECT" ? "Khách không đưa tiền" : "Không chi được";
  const rows = current.data.pending.filter((txn) => txn.type === type);

  return (
    <>
      <h4>Giao dịch chờ kết quả trong ca {current.data.shift_id}</h4>
      <Table<Txn>
        rowKey="txn_id"
        size="small"
        pagination={false}
        dataSource={rows}
        scroll={{ x: true }}
        columns={[
          ...txnColumns,
          {
            title: "Thao tác",
            render: (_, txn) =>
              txn.method === "CASH" ? (
                <Space wrap>
                  <Popconfirm
                    title={`${done} cho ${txn.txn_id}?`}
                    onConfirm={() => confirmCash.mutate({ txn, result: "SUCCESS" })}
                  >
                    <Button size="small" type="primary">
                      {done}
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    title={`${notDone}: giao dịch ${txn.txn_id} thất bại?`}
                    onConfirm={() => confirmCash.mutate({ txn, result: "FAILED" })}
                  >
                    <Button size="small" danger>
                      {notDone}
                    </Button>
                  </Popconfirm>
                </Space>
              ) : (
                <Button size="small" onClick={() => setReconciling(txn)}>
                  Tra soát
                </Button>
              ),
          },
        ]}
      />

      {reconciling && (
        <FormModal<Schemas["Reconcile"]>
          title={`Tra soát giao dịch ${reconciling.txn_id}`}
          initialValues={{ result: "SUCCESS" }}
          onClose={() => setReconciling(null)}
          onSubmit={reconcile.mutateAsync}
        >
          <Form.Item label="Kết quả" name="result" rules={[{ required: true }]}>
            <Select
              options={RESULTS.map((value) => ({ value, label: TXN_STATUS_LABEL[value] }))}
            />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, next) => prev.result !== next.result}
          >
            {({ getFieldValue }) => (
              <Form.Item
                label="Mã tham chiếu"
                name="reference_code"
                rules={[{ required: getFieldValue("result") === "SUCCESS", whitespace: true }]}
              >
                <Input />
              </Form.Item>
            )}
          </Form.Item>
        </FormModal>
      )}
    </>
  );
}
