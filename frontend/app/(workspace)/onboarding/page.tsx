"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { auth } from "@/features/auth/api";
import { ConnectionCards } from "@/components/connection-cards";
import { PreferencesForm } from "@/components/preferences-form";
import { ErrorMessage, PageTitle, Spinner } from "@/components/ui";
export default function Onboarding() {
  const [step, setStep] = useState(0);
  const router = useRouter(),
    cache = useQueryClient();
  const finish = useMutation({
    mutationFn: auth.finish,
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["user"] });
      router.push("/dashboard");
    },
  });
  return (
    <>
      <ol
        aria-label="Setup progress"
        className="mb-10 flex flex-wrap gap-5 text-sm"
      >
        {["Welcome", "Connect tools", "Study preferences", "Ready"].map(
          (label, index) => (
            <li
              key={label}
              aria-current={step === index ? "step" : undefined}
              className={
                step === index ? "font-semibold text-accent" : "text-muted"
              }
            >
              {index + 1}. {label}
            </li>
          ),
        )}
      </ol>
      {step === 0 && (
        <>
          <PageTitle
            eyebrow="Welcome to Relay"
            title="Less scattered. More intentional."
            description="Turn information into understanding, a plan, and actions you approve. Let us set up your workspace."
          />
          <div className="mb-8 grid gap-5 md:grid-cols-3">
            {[
              ["School", "Keep courses and assignments together."],
              ["Work", "Turn meeting notes into project tasks."],
              ["Personal", "Plan goals and next steps in one place."],
            ].map(([title, description]) => (
              <article className="panel" key={title}>
                <h2 className="text-xl font-semibold">{title}</h2>
                <p className="mt-3 text-sm leading-6 text-muted">
                  {description}
                </p>
              </article>
            ))}
          </div>
          <button className="button" onClick={() => setStep(1)}>
            Get started
          </button>
        </>
      )}
      {step === 1 && (
        <>
          <PageTitle
            eyebrow="Step 2"
            title="Bring your tools together."
            description="Connections are optional for local demos. Connect tools now, or skip this step and come back later."
          />
          <ConnectionCards />
          <div className="mt-8 flex gap-3">
            <button className="button secondary" onClick={() => setStep(0)}>
              Back
            </button>
            <button className="button" onClick={() => setStep(2)}>
              Skip for now
            </button>
          </div>
        </>
      )}
      {step === 2 && (
        <>
          <PageTitle
            eyebrow="Step 3"
            title="Find your study rhythm."
            description="Tell Relay when and how you prefer to study. You can change these settings anytime."
          />
          <section className="panel max-w-3xl">
            <PreferencesForm
              label="Save and continue"
              onSaved={() => setStep(3)}
            />
          </section>
          <button className="mt-5 text-sm underline" onClick={() => setStep(1)}>
            Back
          </button>
        </>
      )}
      {step === 3 && (
        <>
          <PageTitle
            eyebrow="Ready when you are"
            title="Your workspace is ready."
            description="Your preferences are saved. Create a project in School, Work, or Personal to get started."
          />
          <button
            className="button"
            disabled={finish.isPending}
            onClick={() => finish.mutate()}
          >
            {finish.isPending && <Spinner label="Finishing onboarding" />}
            {finish.isPending ? "Finishing..." : "Go to dashboard"}
          </button>
          <ErrorMessage error={finish.error} />
        </>
      )}
    </>
  );
}
