import { ConnectionCards } from "@/components/connection-cards";
import { PageTitle } from "@/components/ui";
export default function Connections() {
  return (
    <>
      <PageTitle
        eyebrow="Your tools, connected"
        title="Connections"
        description="Manage the tools Relay can work with. Connecting a tool never gives Relay permission to act without your approval."
      />
      <ConnectionCards />
    </>
  );
}
