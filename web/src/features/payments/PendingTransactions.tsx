// Giao dịch Chờ kết quả trong ca đang mở (TT-02): tiền mặt thì xác nhận đã nhận/đã chi, điện tử thì
// bấm kết quả ngân hàng báo (máy POS, app ngân hàng). Dùng cho thu tiền (3.2) và hoàn tiền (3.4).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Form, Input, Popconfirm, Select, Space, Table, message } from "antd";
import { client, unwrap, type Schemas } from "../../api/client";
import { txnColumns, useCurrentShift } from "../shifts/ShiftsPage";
import { TXN_STATUS_LABEL } from "../../labels";
import { FormModal } from "../../ui";

type Txn = Schemas["Transaction"];
type Result = Schemas["Reconcile"]["result"];

// Kết quả giao dịch đổi ca, đơn, phiếu trả, hóa đơn
export const TXN_KEYS = ["shifts", "orders", "returns"];

const RESULTS = ["SUCCESS", "FAILED"] as const;
const txnPath = (id: string) => ({ params: { path: { txn_id: id } } });
// TT-02 bắt buộc mã tham chiếu khi Thành công; demo không có ngân hàng thật nên tự sinh, không trùng
const fakeReference = (txn: Txn) => `TS-${txn.txn_id}`;

/** Thông báo nổi theo kết quả cuối của giao dịch (thu: đơn Hoàn tất hoặc vẫn Chờ thanh toán). */
function announce(txn: Txn) {
  const collect = txn.type === "COLLECT";
  if (txn.status === "SUCCESS")
    message.success(
      collect
        ? `Thanh toán thành công: đơn ${txn.order_id} Hoàn tất, đã phát hành hóa đơn`
        : `Hoàn tiền thành công: giao dịch ${txn.txn_id}, phiếu trả ${txn.return_id}`,
      5,
    );
  else
    message.error(
      collect
        ? `Giao dịch ${txn.txn_id} thất bại: đơn ${txn.order_id} vẫn Chờ thanh toán, đã nhả hàng giữ, có thể thu lại`
        : `Hoàn tiền ${txn.txn_id} thất bại: phiếu trả ${txn.return_id} vẫn Chưa hoàn, có thể hoàn lại`,
      6,
    );
}

/** Khởi tạo thu (3.2) hoặc hoàn (3.4); xong thì báo nổi bước tiếp theo cho thu ngân. */
export function useStartTxn<V>(start: (values: V) => Promise<Txn>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: start,
    onSuccess: (txn) => {
      const collect = txn.type === "COLLECT";
      message.info(
        txn.method === "CASH"
          ? `Đã tạo giao dịch tiền mặt ${txn.txn_id}: ${collect ? "nhận" : "chi"} tiền xong thì bấm xác nhận ở bảng Giao dịch chờ kết quả`
          : `Đã gửi yêu cầu ${collect ? "thanh toán" : "hoàn tiền"} ${txn.txn_id} sang ngân hàng: có kết quả thì bấm ở bảng Giao dịch chờ kết quả`,
        6,
      );
      TXN_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
    onError: (error) => message.error(error.message, 6),
  });
}

/** Ghi kết quả giao dịch: tiền mặt qua confirm-cash, điện tử qua reconcile; xong thì báo nổi. */
function useResolve() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ txn, result, reference }: { txn: Txn; result: Result; reference?: string | null }) =>
      txn.method === "CASH"
        ? unwrap(client.POST("/transactions/{txn_id}/confirm-cash", { ...txnPath(txn.txn_id), body: { result } }))
        : unwrap(
            client.POST("/transactions/{txn_id}/reconcile", {
              ...txnPath(txn.txn_id),
              body: { result, reference_code: result === "SUCCESS" ? reference || fakeReference(txn) : null },
            }),
          ),
    onSuccess: (txn) => {
      announce(txn);
      TXN_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
    onError: (error) => message.error(error.message, 6),
  });
}

export function PendingTransactions({ type }: { type: Schemas["TxnType"] }) {
  const current = useCurrentShift();
  const resolve = useResolve();

  if (current.isPending) return null;
  if (!current.data)
    return <Alert type="warning" showIcon message="Chưa có ca đang mở: mở ca ở trang Ca thu ngân" />;

  const collect = type === "COLLECT";
  const labels = {
    CASH: collect ? ["Đã nhận đủ tiền", "Khách không đưa tiền"] : ["Đã chi đủ tiền", "Không chi được"],
    ELECTRONIC: ["Ngân hàng báo thành công", "Ngân hàng báo thất bại"],
  };
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
            render: (_, txn) => {
              const [done, notDone] = txn.method === "CASH" ? labels.CASH : labels.ELECTRONIC;
              const busy = resolve.isPending && resolve.variables?.txn.txn_id === txn.txn_id;
              return (
                <Space wrap>
                  <Popconfirm
                    title={`${done} cho ${txn.txn_id}?`}
                    onConfirm={() => resolve.mutate({ txn, result: "SUCCESS" })}
                  >
                    <Button size="small" type="primary" loading={busy}>
                      {done}
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    title={`${notDone}: giao dịch ${txn.txn_id} thất bại?`}
                    onConfirm={() => resolve.mutate({ txn, result: "FAILED" })}
                  >
                    <Button size="small" danger disabled={busy}>
                      {notDone}
                    </Button>
                  </Popconfirm>
                </Space>
              );
            },
          },
        ]}
      />
    </>
  );
}

/** Tra soát giao dịch điện tử Chờ kết quả (TT-02) ở chi tiết ca đã đóng (CA-03). */
export function ReconcileModal({ txn, onClose }: { txn: Txn; onClose: () => void }) {
  const resolve = useResolve();
  return (
    <FormModal<Schemas["Reconcile"]>
      title={`Tra soát giao dịch ${txn.txn_id}`}
      initialValues={{ result: "SUCCESS" }}
      onClose={onClose}
      onSubmit={({ result, reference_code }) =>
        resolve.mutateAsync({ txn, result, reference: reference_code })
      }
    >
      <Form.Item label="Kết quả" name="result" rules={[{ required: true }]}>
        <Select options={RESULTS.map((value) => ({ value, label: TXN_STATUS_LABEL[value] }))} />
      </Form.Item>
      <Form.Item label="Mã tham chiếu" name="reference_code" extra="Để trống thì tự sinh">
        <Input />
      </Form.Item>
    </FormModal>
  );
}
