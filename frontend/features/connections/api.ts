import { z } from "zod";
import { json, request } from "@/lib/api";
import { connectionSchema, Provider } from "@/lib/schemas";

export const notionDestinationSchema = z.object({
  id: z.string(),
  title: z.string(),
  icon_url: z.string().nullable(),
  object_type: z.string(),
});
export type NotionDestination = z.infer<typeof notionDestinationSchema>;

export const connections = {
  list: () => request("/connections", connectionSchema.array()),
  authorize: (provider: Provider) =>
    request(
      `/connections/${provider}/authorize`,
      z.object({ authorization_url: z.url() }),
    ),
  disconnect: (provider: Provider) =>
    request(`/connections/${provider}`, z.undefined(), { method: "DELETE" }),
  notionDestinations: () =>
    request(
      "/connections/NOTION/destinations",
      notionDestinationSchema.array(),
    ),
  refreshNotionDestinations: () =>
    request(
      "/connections/NOTION/destinations/refresh",
      notionDestinationSchema.array(),
      { method: "POST" },
    ),
  selectNotionDestination: (destinationId: string) =>
    request(
      "/connections/NOTION/destinations/default",
      notionDestinationSchema,
      json({ destination_id: destinationId }, "PUT"),
    ),
};
