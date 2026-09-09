import { z } from "zod";
import { request } from "@/lib/api";
import { connectionSchema, Provider } from "@/lib/schemas";
export const connections = {
  list: () => request("/connections", connectionSchema.array()),
  authorize: (provider: Provider) =>
    request(
      `/connections/${provider}/authorize`,
      z.object({ authorization_url: z.url() }),
    ),
  disconnect: (provider: Provider) =>
    request(`/connections/${provider}`, z.undefined(), { method: "DELETE" }),
};
