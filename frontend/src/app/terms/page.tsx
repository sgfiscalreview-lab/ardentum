import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, Section } from "@/components/legal";
import { CONTACT, LEGAL, operatorDetails } from "@/lib/legal";

export const metadata: Metadata = { title: "Terms of Service" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
      <Section title="1. Agreement">
        <p>
          These terms govern your use of Ardentum (the &ldquo;service&rdquo;), operated by {operatorDetails()}. By using the service or signing in, you agree to them. If you do not agree, do not use the service.
        </p>
      </Section>
      <Section title="2. What the service is">
        <p>
          Ardentum is an analytical tool for constructing, optimising, simulating, backtesting and comparing investment portfolios, for education and research. It does not give investment, legal, tax or accounting advice, and nothing in it is a recommendation to buy or sell any security.
        </p>
        <p>
          Results are estimates computed from historical data and the assumptions shown with each result. They can be wrong, and past performance does not predict future results. You are responsible for any decision you make using the service. The demo dataset is synthetic: its assets do not exist.
        </p>
      </Section>
      <Section title="3. Accounts">
        <p>
          You must be at least 16 years old to create an account. You can use the workspace without an account. Saving portfolios, uploading data and saving ESG overlays require signing in with a supported provider (for example Google or GitHub). You are responsible for activity under your account. You can export or delete your account at any time from the <Link href="/account" className="underline underline-offset-2">Account</Link> page.
        </p>
      </Section>
      <Section title="4. Your content">
        <p>
          You keep all rights to the data you upload and the portfolios you create. You grant the operator permission to store and process that content only to provide the service to you. You confirm that you have the right to upload and analyse any data you provide, including under the licence of any data vendor.
        </p>
      </Section>
      <Section title="5. Acceptable use">
        <p>
          Do not attempt to disrupt the service, bypass its rate limits or security, access other users&apos; data, upload unlawful content or malware, or use the service to break any law. The operator may suspend access that threatens the service or other users.
        </p>
      </Section>
      <Section title="6. Third-party data">
        <p>
          The service uses public data sources, each subject to its own terms: the Kenneth R. French Data Library (Tuck School of Business, Dartmouth), European Central Bank reference rates served by Frankfurter, central-bank policy rates from the Bank for International Settlements, WikiRate (licensed CC BY 4.0) and, where enabled, FRED (Federal Reserve Bank of St. Louis) and Tiingo. Attribution is shown with the results that use them. The operator does not guarantee the accuracy, completeness or availability of third-party data.
        </p>
      </Section>
      <Section title="7. Fees and refunds">
        <p>
          The service is free. There are no subscriptions, paid features, trial periods or hidden charges, and you are never asked for payment details, so there is nothing to refund. If paid features are ever offered, their prices will be shown before you choose them and nothing will be charged without your explicit agreement; refund terms will be published before then.
        </p>
      </Section>
      <Section title="8. Open-source software and licences">
        <p>
          Ardentum is built with open-source software, used under the licences listed on the <Link href="/licences" className="underline underline-offset-2">Licences</Link> page, which also lists the licence of each data source.
        </p>
      </Section>
      <Section title="9. Availability and changes">
        <p>
          The service may change, be interrupted or be discontinued at any time. The operator may update these terms; the date above shows the latest version, and continued use after a change means you accept it.
        </p>
      </Section>
      <Section title="10. No warranty and limitation of liability">
        <p>
          The service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo;, without warranties of any kind, to the extent permitted by law. To the extent permitted by law, the operator is not liable for indirect or consequential losses, lost profits or investment losses arising from your use of the service. Nothing in these terms limits liability that cannot be limited by law.
        </p>
      </Section>
      <Section title="11. Ending your use">
        <p>You can stop using the service and delete your account at any time. The operator may close accounts that breach these terms.</p>
      </Section>
      <Section title="12. Governing law and contact">
        <p>
          {LEGAL.governingLaw ? `These terms are governed by the laws of ${LEGAL.governingLaw}.` : "The governing law is set by the operator."} Questions about these terms: {CONTACT}.
        </p>
      </Section>
    </LegalPage>
  );
}
