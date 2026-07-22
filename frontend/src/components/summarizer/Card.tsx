import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

/** Shared card shell: 16px radius, 24px padding, white bg, border, faint shadow that deepens on hover. */
export function Card({ children, className = "" }: CardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      whileHover={{ scale: 1.01 }}
      className={`rounded-2xl border border-border bg-card p-6 shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-shadow hover:shadow-md ${className}`}
    >
      {children}
    </motion.section>
  );
}

export function SectionTitle({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <h3 className="mb-4 flex items-center gap-2 text-xl font-semibold text-text">
      {icon}
      {children}
    </h3>
  );
}

/** Neutral pill for keywords/tags — the palette stays to Primary + neutrals, no rainbow of tag colors. */
export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "primary" | "mono" }) {
  const toneClasses =
    tone === "primary"
      ? "bg-primary/10 text-primary"
      : tone === "mono"
        ? "border border-border bg-transparent text-subtext"
        : "bg-black/[0.04] text-text";
  return <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${toneClasses}`}>{children}</span>;
}
