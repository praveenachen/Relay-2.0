"use client";

import {
  QueryClient,
  QueryClientProvider,
  useIsMutating,
} from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "@/components/ui";

function GlobalMutationActivity() {
  const activeMutations = useIsMutating();
  if (!activeMutations) return null;
  return (
    <div className="global-action-progress" role="status" aria-live="polite">
      <Spinner label="Relay is working" />
      <span>Working…</span>
    </div>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <GlobalMutationActivity />
      {children}
    </QueryClientProvider>
  );
}
