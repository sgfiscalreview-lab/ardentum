/**
 * Operator details shown in the Terms of Service, Privacy Policy and site footer. Set at
 * build time (see DEPLOYMENT.md and docs/SETUP_GUIDE.md). Missing required values are
 * reported on the legal pages so an unconfigured deployment is obvious.
 */
export const LEGAL = {
  operator: process.env.NEXT_PUBLIC_LEGAL_OPERATOR?.trim() || "",
  contactEmail: process.env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL?.trim() || "",
  governingLaw: process.env.NEXT_PUBLIC_LEGAL_GOVERNING_LAW?.trim() || "",
  // Optional: postal address and company registration (needed where a business must
  // publish them, e.g. the EU and UK).
  address: process.env.NEXT_PUBLIC_LEGAL_ADDRESS?.trim() || "",
  registration: process.env.NEXT_PUBLIC_LEGAL_REGISTRATION?.trim() || "",
  lastUpdated: process.env.NEXT_PUBLIC_LEGAL_LAST_UPDATED?.trim() || "2026-09-30",
};

/** Public source repository (MIT licence). */
export const SOURCE_URL = "https://github.com/sgfiscalreview-lab/ardentum";

export const LEGAL_CONFIGURED = Boolean(LEGAL.operator && LEGAL.contactEmail && LEGAL.governingLaw);

export const OPERATOR = LEGAL.operator || "the operator of this website";
export const CONTACT = LEGAL.contactEmail || "the contact address published by the operator";

/** "Name, registration, address" for the places that identify the operator in full. */
export function operatorDetails(): string {
  return [LEGAL.operator || OPERATOR, LEGAL.registration, LEGAL.address].filter(Boolean).join(", ");
}
