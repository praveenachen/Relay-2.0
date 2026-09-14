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
  // Existing databases the connection can see, for Collaborate's project
  // setup to pick one to sync action items into. Unlike destinations
  // (pages), this is never persisted/selected as a workflow default --
  // just a live list, so there's no refresh/select pair.
  notionTaskDatabases: () =>
    request(
      "/connections/NOTION/task-databases",
      notionDestinationSchema.array(),
    ),
  githubRepositories: () =>
    request("/connections/GITHUB/repositories", githubRepositorySchema.array()),
};
