// 3.3 Xem và in lại hóa đơn của đơn đã thanh toán; mỗi lần in API tăng số lần in (TT-04).
// Trang in dùng hộp thoại in của trình duyệt; khi in chỉ hiện phần hóa đơn.
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Descriptions, Modal, Table, Tag } from "antd";
import { useState } from "react";
import { createPortal } from "react-dom";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime, money } from "../../format";
import { ORDER_STATUS_LABEL, TXN_METHOD_LABEL } from "../../labels";
import { moneyColumn, useWrite } from "../../ui";

type Order = Schemas["Order"];
type Invoice = Schemas["Invoice"];

// Đơn đã thanh toán thành công đều có hóa đơn, kể cả khi sau đó có trả hàng
const PAID: Order["status"][] = ["COMPLETED", "PARTIALLY_RETURNED", "FULLY_RETURNED"];

// Bản in nằm ngay dưới <body>: trên màn hình ẩn; khi in chỉ hiện bản này
const PRINT_CSS = `.invoice-print { display: none; }
@media print {
  body > :not(.invoice-print) { display: none !important; }
  .invoice-print { display: block; }
}`;

function InvoiceView({ invoice }: { invoice: Invoice }) {
  return (
    <>
      <h3>Hóa đơn {invoice.invoice_no}</h3>
      <Descriptions size="small" column={1}>
        <Descriptions.Item label="Đơn hàng">{invoice.order_id}</Descriptions.Item>
        <Descriptions.Item label="Chi nhánh">{invoice.branch_id}</Descriptions.Item>
        <Descriptions.Item label="Phát hành lúc">{dateTime(invoice.issued_at)}</Descriptions.Item>
        <Descriptions.Item label="Phương thức">{TXN_METHOD_LABEL[invoice.method]}</Descriptions.Item>
        <Descriptions.Item label="Số lần in">{invoice.print_count}</Descriptions.Item>
      </Descriptions>
      <Table<Schemas["InvoiceLine"]>
        rowKey="product_id"
        size="small"
        pagination={false}
        dataSource={invoice.items}
        columns={[
          { title: "Sản phẩm", dataIndex: "name" },
          { title: "SL", dataIndex: "quantity", align: "right" },
          moneyColumn("Đơn giá", "unit_price"),
          moneyColumn("Thành tiền", "amount"),
        ]}
      />
      <h3 style={{ textAlign: "right" }}>Tổng tiền: {money(invoice.total)}</h3>
    </>
  );
}

export function InvoicesPage() {
  const orders = useQuery({
    queryKey: ["orders", undefined],
    queryFn: () => unwrap(client.GET("/orders", { params: { query: {} } })),
  });
  const [orderId, setOrderId] = useState<string | null>(null);
  const invoice = useQuery({
    queryKey: ["invoice", orderId],
    queryFn: () =>
      unwrap(
        client.GET("/orders/{order_id}/invoice", { params: { path: { order_id: orderId! } } }),
      ),
    enabled: orderId !== null,
  });
  const print = useWrite(
    (invoiceNo: string) =>
      unwrap(client.POST("/invoices/{invoice_no}/print", { params: { path: { invoice_no: invoiceNo } } })),
    ["invoice"],
  );

  // Ghi nhận lần in trước rồi mới mở hộp thoại in, để bản in mang đúng số lần in
  const runPrint = async (invoiceNo: string) => {
    try {
      await print.mutateAsync(invoiceNo);
    } catch {
      return; // Lỗi đã được useWrite báo; không in khi API chưa ghi nhận
    }
    await invoice.refetch();
    window.print();
  };

  return (
    <Card title="Hóa đơn">
      <Table<Order>
        rowKey="order_id"
        loading={orders.isPending}
        dataSource={(orders.data ?? []).filter((order) => PAID.includes(order.status))}
        scroll={{ x: true }}
        columns={[
          { title: "Mã đơn", dataIndex: "order_id" },
          { title: "Khách", dataIndex: "customer_id" },
          { title: "Hoàn tất lúc", dataIndex: "completed_at", render: dateTime },
          {
            title: "Trạng thái",
            dataIndex: "status",
            render: (v: Order["status"]) => <Tag>{ORDER_STATUS_LABEL[v]}</Tag>,
          },
          moneyColumn("Tổng tiền", "total"),
          {
            title: "Thao tác",
            render: (_, order) => (
              <Button size="small" onClick={() => setOrderId(order.order_id)}>
                Xem hóa đơn
              </Button>
            ),
          },
        ]}
      />

      {orderId && (
        <Modal
          open
          width={720}
          title={`Hóa đơn của đơn ${orderId}`}
          onCancel={() => setOrderId(null)}
          footer={[
            <Button key="close" onClick={() => setOrderId(null)}>
              Đóng
            </Button>,
            <Button
              key="print"
              type="primary"
              disabled={!invoice.data}
              loading={print.isPending}
              onClick={() => runPrint(invoice.data!.invoice_no)}
            >
              In hóa đơn
            </Button>,
          ]}
        >
          {invoice.error && <p>{invoice.error.message}</p>}
          {invoice.data && <InvoiceView invoice={invoice.data} />}
        </Modal>
      )}
      {orderId && invoice.data && createPortal(
        <div className="invoice-print">
          <style>{PRINT_CSS}</style>
          <InvoiceView invoice={invoice.data} />
        </div>,
        document.body,
      )}
    </Card>
  );
}
