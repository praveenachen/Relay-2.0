import { json, request } from "@/lib/api";
import { Approval, approvalSchema } from "@/lib/schemas";
export const approvals = {
  pending: () =>
    request("/approvals?status=PENDING&limit=100", approvalSchema.array()),
  list: () => request("/approvals", approvalSchema.array()),
  resolve: (approval: Approval, approve: boolean) =>
    request(
      `/approvals/${approval.id}/${approve ? "approve" : "reject"}`,
      approvalSchema,
      approve
        ? json({ approved_payload: approval.original_payload })
        : { method: "POST" },
    ),
};
