import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, Section } from "@/components/legal";
import { CONTACT, operatorDetails } from "@/lib/legal";

export const metadata: Metadata = { title: "Privacy Policy" };

const link = "underline underline-offset-2";

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <Section title="1. Who is responsible">
        <p>
          Ardentum is operated by {operatorDetails()}, which decides how the personal data described here is used (the data controller). Contact: {CONTACT}.
        </p>
      </Section>
      <Section title="2. What is collected">
        <p>Ardentum collects only what it needs to run the service. It never asks for your name, phone number, postal address, date of birth or payment details.</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>
            <strong className="text-ink">Account.</strong> When you sign in with Google or GitHub, the sign-in service (Supabase) receives your email address, an account identifier and basic profile details from that provider. The Ardentum database stores only the account identifier and your email address.
          </li>
          <li>
            <strong className="text-ink">Content you create.</strong> Price files and asset metadata you upload, portfolios you save, ESG overlays you build, and the inputs and results of background calculations.
          </li>
          <li>
            <strong className="text-ink">Technical data.</strong> Server logs record each request&apos;s method, path, status, duration and a random request id; they do not record your IP address. To limit how many calculations one client can run per minute, the API counts requests per account when you are signed in and otherwise per IP address. The address is stored only as a keyed hash that changes every day and cannot be turned back into the address. The hosting providers may keep their own access logs.
          </li>
          <li>
            <strong className="text-ink">Usage counts.</strong> Each time a calculation, save or export finishes successfully, the server adds one to a daily total for that kind of action. Only the date, the kind and the total are stored, with nothing about who, from where or on what device, so they are not personal data. The totals are published on the <Link href="/usage" className={link}>Usage</Link> page.
          </li>
          <li>
            <strong className="text-ink">Browser storage.</strong> Your browser keeps your workspace settings, your theme choice and, when you are signed in, your session tokens. Ardentum sets no cookies and uses no analytics, advertising or tracking scripts. The <Link href="/cookies" className={link}>Cookie Policy</Link> lists each item.
          </li>
        </ul>
      </Section>
      <Section title="3. Why it is used, and the legal basis">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>To sign you in, store your content and run the calculations you ask for: necessary to provide the service you requested (performance of a contract).</li>
          <li>To keep the service secure and available (rate limiting, investigating errors and abuse): the operator&apos;s legitimate interest in a working, safe service.</li>
          <li>To comply with the law where it requires the operator to keep or disclose data: legal obligation.</li>
        </ul>
        <p>
          Your data is not sold, rented, shared for advertising or used to build a profile of you. No decision with legal or similar effects is made about you by automated means.
        </p>
      </Section>
      <Section title="4. Who processes it">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Supabase: database and sign-in.</li>
          <li>Render: runs the Ardentum API (servers in Singapore).</li>
          <li>Cloudflare: serves the website.</li>
          <li>Google and GitHub: only when you choose them to sign in.</li>
        </ul>
        <p>
          These providers act on the operator&apos;s instructions under their data processing terms. To compute results, the API requests public data from the Kenneth R. French Data Library, Frankfurter (European Central Bank rates), the Bank for International Settlements and WikiRate and, where the operator has enabled them, FRED and Tiingo. These requests contain no personal data; when you build ESG scores, the ISINs and company names you work with are sent to WikiRate as search terms.
        </p>
      </Section>
      <Section title="5. International transfers">
        <p>
          The providers above may process data in countries other than yours, including Singapore and the United States. Where the law requires safeguards for such transfers, they rely on the providers&apos; data processing terms, which include the European Commission&apos;s standard contractual clauses.
        </p>
      </Section>
      <Section title="6. How long it is kept">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Account data and content: until you delete them or your account.</li>
          <li>Background calculation results: 24 hours.</li>
          <li>Rate-limit counters: a few minutes.</li>
          <li>Daily usage totals (no personal data): indefinitely.</li>
          <li>Hosting providers&apos; logs: for the period set by each provider.</li>
        </ul>
        <p>Deleted data can remain in the database provider&apos;s backups until those backups expire.</p>
      </Section>
      <Section title="7. Security">
        <p>
          All traffic is encrypted (HTTPS). Every request for your content is checked against your signed-in account, so other users cannot read it. Service keys stay on the server and are never sent to your browser.
        </p>
      </Section>
      <Section title="8. Your rights">
        <p>
          On the <Link href="/account" className={link}>Account</Link> page you can download everything Ardentum stores about you (JSON) and permanently delete your account and all your content, at any time and without contacting anyone.
        </p>
        <p>
          You can also write to {CONTACT} to access, correct, export or delete your data, to restrict or object to its use, or to withdraw a consent. For a deletion request, write from the email address of your account, or say which address it is, so the request can be matched to it. Requests are answered within one month.
        </p>
        <p>
          Depending on where you live, you may complain to your data-protection authority. Residents of California: Ardentum does not sell or share personal information as those terms are defined by California law.
        </p>
      </Section>
      <Section title="9. Emails">
        <p>
          Ardentum sends no newsletters or marketing emails. If email sign-in is enabled, the sign-in service sends only the messages your account needs (confirming an address, resetting a password). If marketing emails are ever introduced, they will be sent only to people who opt in and will contain a link to unsubscribe.
        </p>
      </Section>
      <Section title="10. Children">
        <p>
          You must be at least 16 years old to create an account. The service is not directed at children and does not knowingly collect their data. If you believe a child has created an account, write to {CONTACT} and the account will be deleted.
        </p>
      </Section>
      <Section title="11. Changes">
        <p>Changes to this policy are published on this page with a new date.</p>
      </Section>
    </LegalPage>
  );
}
