import { Suspense } from "react";
import { ProjectWorkspace } from "@/components/project-workspace";
import { Loading } from "@/components/ui";

export default function ProjectPage() {
  return <Suspense fallback={<Loading label="Loading project" />}><ProjectWorkspace /></Suspense>;
}
