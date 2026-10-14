"use client";

import { domMax, LazyMotion, MotionConfig } from "motion/react";
import type { ReactNode } from "react";

import { SPRING } from "@/lib/motion";

/**
 * Motion for the whole site: springs by default (they start from the value on screen and
 * keep their velocity when redirected), and the user's reduced-motion setting respected,
 * which turns movement into fades. `strict` keeps components on the lightweight `m.*` API.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domMax} strict>
      <MotionConfig reducedMotion="user" transition={SPRING}>
        {children}
      </MotionConfig>
    </LazyMotion>
  );
}
