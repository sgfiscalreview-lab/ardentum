import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, Section } from "@/components/legal";
import { Table, Td, Th } from "@/components/ui";
import { CONTACT } from "@/lib/legal";

import { ClearStorage } from "./clear-storage";

export const metadata: Metadata = { title: "Cookie Policy" };

const ITEMS = [
  {
    name: "ardentum.theme",
    purpose: "Remembers the light or dark theme you chose.",
    when: "Only after you choose a theme",
    kept: "Until you choose the system theme again or clear it",
  },
  {
    name: "ardentum.workspace",
    purpose: "Keeps your workspace settings (dataset, date window, estimators, constraints) when you reload the page.",
    when: "When you use the workspace",
    kept: "Until you clear it",
  },
  {
    name: "sb-…-auth-token",
    purpose: "Keeps you signed in: the session tokens issued by the sign-in service (Supabase).",
    when: "Only while you are signed in",
    kept: "Removed when you sign out",
  },
];

export default function CookiesPage() {
  return (
    <LegalPage title="Cookie Policy">
      <Section title="1. Summary">
        <p>
          Ardentum sets no cookies. It uses no analytics, advertising, social-media or tracking scripts, and loads no fonts or scripts from third parties. It stores the few items below in your browser&apos;s local storage, each needed for something you asked for.
        </p>
      </Section>
      <Section title="2. What is stored in your browser">
        <div className="rounded-sm border border-line">
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Purpose</Th>
                <Th>Stored</Th>
                <Th>Kept</Th>
              </tr>
            </thead>
            <tbody>
              {ITEMS.map((i) => (
                <tr key={i.name}>
                  <Td>
                    <code className="text-xs">{i.name}</code>
                  </Td>
                  <Td>{i.purpose}</Td>
                  <Td>{i.when}</Td>
                  <Td>{i.kept}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
        <p>These items stay on your device. Only the session token is sent to the Ardentum API, to prove who you are.</p>
      </Section>
      <Section title="3. Why there is no consent banner">
        <p>
          Every item above is strictly necessary for a service you requested, or remembers a choice you made. Under the EU ePrivacy rules and the UK PECR, such storage does not need consent. If Ardentum ever adds storage that is not strictly necessary, such as analytics, it will ask for your consent first and let you refuse as easily as you accept.
        </p>
      </Section>
      <Section title="4. Hosting providers">
        <p>
          The companies that host the website and the API may set their own strictly necessary security cookies to protect the service against abuse. They are not used to track you.
        </p>
      </Section>
      <Section title="5. Removing stored data">
        <p>
          Signing out removes the session token. The button below removes your theme and workspace settings from this browser. You can also clear site data in your browser&apos;s settings at any time.
        </p>
        <ClearStorage />
      </Section>
      <Section title="6. Questions">
        <p>
          The <Link href="/privacy" className="underline underline-offset-2">Privacy Policy</Link> explains how personal data is used. Contact: {CONTACT}.
        </p>
      </Section>
    </LegalPage>
  );
}
