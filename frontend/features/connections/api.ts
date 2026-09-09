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

export const calendarListItemSchema = z.object({
  id: z.string(),
  summary: z.string(),
  primary: z.boolean(),
  time_zone: z.string().nullable(),
});
export type CalendarListItem = z.infer<typeof calendarListItemSchema>;

export const notionTaskDatabaseSchema = z.object({
  id: z.string(),
  title: z.string(),
});
export type NotionTaskDatabase = z.infer<typeof notionTaskDatabaseSchema>;

export const notionTaskPropertyMappingSchema = z.object({
  title: z.string().min(1),
  course: z.string().nullable().optional(),
  deadline: z.string().min(1),
  priority: z.string().nullable().optional(),
  estimated_minutes: z.string().min(1),
  status: z.string().nullable().optional(),
  completed_statuses: z.array(z.string()).optional(),
  estimate_unit: z.enum(["minutes", "hours"]).optional(),
});
export type NotionTaskPropertyMapping = z.infer<
  typeof notionTaskPropertyMappingSchema
>;

export const githubRepositorySchema = z.object({
  owner: z.string(),
  name: z.string(),
  full_name: z.string(),
  private: z.boolean(),
  html_url: z.string(),
});
export type GitHubRepository = z.infer<typeof githubRepositorySchema>;

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
  googleCalendars: () =>
    request("/connections/GOOGLE/calendars", calendarListItemSchema.array()),
  refreshGoogleCalendars: () =>
    request(
      "/connections/GOOGLE/calendars/refresh",
      calendarListItemSchema.array(),
      { method: "POST" },
    ),
  selectGoogleCalendar: (calendarId: string) =>
    request(
      "/connections/GOOGLE/calendars/default",
      calendarListItemSchema,
      json({ destination_id: calendarId }, "PUT"),
    ),
  notionTaskDatabases: () =>
    request(
      "/connections/NOTION/task-databases",
      notionTaskDatabaseSchema.array(),
    ),
  refreshNotionTaskDatabases: () =>
    request(
      "/connections/NOTION/task-databases/refresh",
      notionTaskDatabaseSchema.array(),
      { method: "POST" },
    ),
  selectNotionTaskDatabase: (
    databaseId: string,
    mapping: NotionTaskPropertyMapping,
  ) =>
    request(
      "/connections/NOTION/task-databases/default",
      notionTaskDatabaseSchema,
      json({ database_id: databaseId, mapping }, "PUT"),
    ),
  githubRepositories: () =>
    request("/connections/GITHUB/repositories", githubRepositorySchema.array()),
};
