/**
 * Operator details shown in the Terms of Service and Privacy Policy. Set at build time
 * (see DEPLOYMENT.md and docs/SETUP_GUIDE.md). Missing values are reported on the pages
 * so an unconfigured deployment is obvious.
 */
export const LEGAL = {
  operator: process.env.NEXT_PUBLIC_LEGAL_OPERATOR?.trim() || "",
  contactEmail: process.env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL?.trim() || "",
  governingLaw: process.env.NEXT_PUBLIC_LEGAL_GOVERNING_LAW?.trim() || "",
  lastUpdated: process.env.NEXT_PUBLIC_LEGAL_LAST_UPDATED?.trim() || "2026-09-26",
};

export const LEGAL_CONFIGURED = Boolean(LEGAL.operator && LEGAL.contactEmail && LEGAL.governingLaw);

export const OPERATOR = LEGAL.operator || "the operator of this website";
export const CONTACT = LEGAL.contactEmail || "the contact address published by the operator";
