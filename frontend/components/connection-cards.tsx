"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useConnections } from "@/hooks/queries";
import { connections } from "@/features/connections/api";
import { Provider } from "@/lib/schemas";
import { ErrorMessage, Loading, Status } from "@/components/ui";

const tools: {
  provider: Provider;
  name: string;
  description: string;
  symbol: string;
}[] = [
  {
    provider: "GOOGLE",
    name: "Google Calendar",
    description: "Make space for study alongside your existing commitments.",
    symbol: "G",
  },
  {
    provider: "NOTION",
    name: "Notion",
    description:
      "Keep structured notes and shared action items in your workspace.",
    symbol: "N",
  },
  {
    provider: "GITHUB",
    name: "GitHub",
    description: "Connect project decisions with technical work.",
    symbol: "GH",
  },
];
export function ConnectionCards() {
  const query = useConnections();
  const cache = useQueryClient();
  const [confirm, setConfirm] = useState<Provider | null>(null);
  const connect = useMutation({ mutationFn: connections.authorize });
  const destinations = useMutation({
    mutationFn: connections.refreshNotionDestinations,
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["connections"] });
    },
  });
  const selectDestination = useMutation({
    mutationFn: connections.selectNotionDestination,
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["connections"] });
    },
  });
  const disconnect = useMutation({
    mutationFn: connections.disconnect,
    onSuccess: async () => {
      setConfirm(null);
      await cache.invalidateQueries({ queryKey: ["connections"] });
    },
  });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorMessage error={query.error} />;
  return (
    <>
      <p className="notice mb-6">
        Notion, Google Calendar, and GitHub all connect through OAuth and store
        encrypted credentials. GitHub uses repository-scoped access only -- no
        administration, deletion, or Actions permissions.
      </p>
      <div className="grid gap-5 md:grid-cols-3">
        {tools.map((tool) => {
          const accounts = query.data.filter(
            (account) =>
              account.provider === tool.provider &&
              account.status !== "REVOKED",
          );
          const connecting =
            connect.isPending && connect.variables === tool.provider;
          return (
            <article key={tool.provider} className="panel flex flex-col">
              <span className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl border border-line font-semibold">
                {tool.symbol}
              </span>
              <h3 className="text-lg font-semibold">{tool.name}</h3>
              <p className="mb-6 mt-3 text-sm leading-6 text-muted">
                {tool.description}
              </p>
              <div className="mt-auto">
                {accounts.length ? (
                  accounts.map((account) => (
                    <div key={account.id} className="mb-4">
                      <Status value={account.status} />
                      <p className="mt-3 break-words text-sm">
                        Connected as {account.display_name}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {account.scopes.join(", ") || "No scopes recorded"}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="mb-4 text-sm text-muted">Not connected</p>
                )}
                {accounts.length ? (
                  confirm === tool.provider ? (
                    <div className="space-y-3">
                      <p className="text-sm">
                        Remove all {tool.name} connections and stored
                        credentials from Relay?
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="button"
                          disabled={disconnect.isPending}
                          onClick={() => disconnect.mutate(tool.provider)}
                        >
                          Confirm disconnect
                        </button>
                        <button
                          className="button secondary"
                          onClick={() => setConfirm(null)}
                        >
                          Keep connection
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      className="button secondary"
                      onClick={() => setConfirm(tool.provider)}
                    >
                      Disconnect
                    </button>
                  )
                ) : (
                  <button
                    className="button secondary"
                    disabled={connect.isPending}
                    onClick={() =>
                      connect.mutate(tool.provider, {
                        onSuccess: (data) => {
                          window.location.href = data.authorization_url;
                        },
                      })
                    }
                  >
                    {connecting ? "Connecting..." : "Connect"}
                  </button>
                )}
                {tool.provider === "NOTION" && accounts.length > 0 && (
                  <NotionDestinationPicker
                    account={accounts[0]}
                    loading={
                      destinations.isPending || selectDestination.isPending
                    }
                    refresh={() => destinations.mutate()}
                    destinations={destinations.data || []}
                    select={(id) => selectDestination.mutate(id)}
                  />
                )}
                {tool.provider === "GOOGLE" && accounts.length > 0 && (
                  <GoogleCalendarPicker account={accounts[0]} />
                )}
              </div>
            </article>
          );
        })}
      </div>
      <div className="mt-5">
        <ErrorMessage
          error={
            connect.error ||
            disconnect.error ||
            destinations.error ||
            selectDestination.error
          }
        />
      </div>
    </>
  );
}

function NotionDestinationPicker({
  account,
  loading,
  destinations,
  refresh,
  select,
}: {
  account: {
    provider_metadata: Record<string, unknown>;
  };
  loading: boolean;
  destinations: { id: string; title: string }[];
  refresh: () => void;
  select: (id: string) => void;
}) {
  const selected =
    typeof account.provider_metadata.default_destination_title === "string"
      ? account.provider_metadata.default_destination_title
      : undefined;
  return (
    <div className="mt-5 border-t border-line pt-5">
      <p className="text-sm font-medium">Default lecture notes destination</p>
      <p className="mt-2 text-sm text-muted">
        {selected || "No default destination selected"}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          className="button secondary"
          disabled={loading}
          onClick={refresh}
        >
          Refresh pages
        </button>
        {destinations.length > 0 && (
          <select
            className="min-h-11 rounded-md border border-line bg-surface px-3 text-sm"
            disabled={loading}
            defaultValue=""
            onChange={(event) =>
              event.target.value && select(event.target.value)
            }
          >
            <option value="">Choose destination</option>
            {destinations.map((destination) => (
              <option key={destination.id} value={destination.id}>
                {destination.title}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

function GoogleCalendarPicker({
  account,
}: {
  account: { provider_metadata: Record<string, unknown> };
}) {
  const cache = useQueryClient();
  const calendars = useQuery({
    queryKey: ["connections", "google-calendars"],
    queryFn: connections.googleCalendars,
  });
  const invalidate = () =>
    cache.invalidateQueries({ queryKey: ["connections"] });
  const refresh = useMutation({
    mutationFn: connections.refreshGoogleCalendars,
    onSuccess: async (data) => {
      cache.setQueryData(["connections", "google-calendars"], data);
      await invalidate();
    },
  });
  const select = useMutation({
    mutationFn: connections.selectGoogleCalendar,
    onSuccess: invalidate,
  });
  const selected =
    typeof account.provider_metadata.default_calendar_summary === "string"
      ? account.provider_metadata.default_calendar_summary
      : undefined;
  const loading = refresh.isPending || select.isPending;
  const items = calendars.data || [];
  return (
    <div className="mt-5 border-t border-line pt-5">
      <p className="text-sm font-medium">Calendar Relay schedules into</p>
      <p className="mt-2 text-sm text-muted">
        {selected || "No calendar selected"}
      </p>
      <ErrorMessage error={calendars.error || refresh.error || select.error} />
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          className="button secondary"
          disabled={loading}
          onClick={() => refresh.mutate()}
        >
          Refresh calendars
        </button>
        {items.length > 0 && (
          <select
            className="min-h-11 rounded-md border border-line bg-surface px-3 text-sm"
            disabled={loading}
            defaultValue=""
            onChange={(event) =>
              event.target.value && select.mutate(event.target.value)
            }
          >
            <option value="">Choose calendar</option>
            {items.map((calendar) => (
              <option key={calendar.id} value={calendar.id}>
                {calendar.summary}
                {calendar.primary ? " (primary)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}
