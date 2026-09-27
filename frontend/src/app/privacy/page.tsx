import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, Section } from "@/components/legal";
import { CONTACT, OPERATOR } from "@/lib/legal";

export const metadata: Metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <Section title="1. Who is responsible">
        <p>
          Ardentum is operated by {OPERATOR}, which decides how the personal data described here is used. Contact: {CONTACT}.
        </p>
      </Section>
      <Section title="2. What is collected">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>
            <strong className="text-ink">Account.</strong> When you sign in with Google or GitHub, the sign-in service (Supabase) receives your email address, an account identifier and basic profile details from that provider. The Ardentum database stores only the account identifier and your email address.
          </li>
          <li>
            <strong className="text-ink">Content you create.</strong> Price files and asset metadata you upload, portfolios you save, ESG overlays you build, and the inputs and results of background calculations.
          </li>
          <li>
            <strong className="text-ink">Technical data.</strong> Server logs record each request&apos;s method, path, status, duration and a random request id. Your IP address, or your account identifier when signed in, is used in short-lived counters that limit how many calculations one client can run per minute. The hosting providers may keep their own access logs.
          </li>
          <li>
            <strong className="text-ink">Browser storage.</strong> Your browser keeps your workspace settings, theme choice and, when signed in, your session tokens in local storage. There are no advertising cookies, analytics or tracking scripts.
          </li>
        </ul>
      </Section>
      <Section title="3. Why it is used">
        <p>
          To provide the service you ask for (signing you in, storing and computing your portfolios), to keep it secure and available (rate limiting, error investigation) and to meet legal obligations. Your data is not sold, rented or used for advertising.
        </p>
      </Section>
      <Section title="4. Who processes it">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Supabase: database and sign-in.</li>
          <li>Google Cloud: runs the Ardentum API.</li>
          <li>Cloudflare: serves the website.</li>
          <li>Google and GitHub: only when you choose them to sign in.</li>
        </ul>
        <p>
          To compute results, the API requests public data from the Kenneth R. French Data Library, Frankfurter (ECB rates), FRED and WikiRate. These requests contain no personal data; when you build ESG scores, the ISINs and company names you work with are sent to WikiRate as search terms. These providers may process data in countries other than yours.
        </p>
      </Section>
      <Section title="5. How long it is kept">
        <p>
          Account data and content are kept until you delete them or your account. Background calculation results are deleted after 24 hours. Rate-limit counters are deleted automatically after they expire.
        </p>
      </Section>
      <Section title="6. Your rights">
        <p>
          On the <Link href="/account" className="underline underline-offset-2">Account</Link> page you can download everything Ardentum stores about you (JSON) and permanently delete your account and all your content. You can also contact {CONTACT} to access, correct or delete your data, or to object to its use. Depending on where you live, you may complain to your data-protection authority.
        </p>
      </Section>
      <Section title="7. Children">
        <p>The service is not directed at children under 16, and they should not create an account.</p>
      </Section>
      <Section title="8. Changes">
        <p>Changes to this policy are published on this page with a new date.</p>
      </Section>
    </LegalPage>
  );
}
