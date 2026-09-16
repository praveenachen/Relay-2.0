"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useConnections } from "@/hooks/queries";
import { connections } from "@/features/connections/api";
import { Provider } from "@/lib/schemas";
import { ErrorMessage, Loading, Spinner, Status } from "@/components/ui";

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
                          {disconnect.isPending && (
                            <Spinner label={`Disconnecting ${tool.name}`} />
                          )}
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
                    {connecting && (
                      <Spinner label={`Connecting ${tool.name}`} />
                    )}
                    {connecting ? "Connecting..." : "Connect"}
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <div className="mt-5">
        <ErrorMessage error={connect.error || disconnect.error} />
      </div>
    </>
  );
}
