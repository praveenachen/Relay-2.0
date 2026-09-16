"use client";

import { useParams, notFound } from "next/navigation";
import {
  NewProjectButton,
  ProjectLibrary,
  spaceDetails,
  type Space,
} from "@/components/project-library";

const spaces: Record<string, Space> = {
  school: "SCHOOL",
  work: "WORK",
  personal: "PERSONAL",
};

export default function SpacePage() {
  const params = useParams<{ space: string }>();
  const space = spaces[params.space];
  if (!space) notFound();
  const detail = spaceDetails[space];
  return (
    <>
      <header className={`space-hero ${space.toLowerCase()}`}>
        <div>
          <p className="eyebrow">Space</p>
          <h1>{detail.title}</h1>
          <p>{detail.description}</p>
        </div>
        <NewProjectButton initialSpace={space} />
      </header>
      <section>
        <div className="product-section-heading">
          <div>
            <h2>Your projects</h2>
            <p>Everything in progress, all in one view.</p>
          </div>
        </div>
        <ProjectLibrary space={space} />
      </section>
    </>
  );
}
