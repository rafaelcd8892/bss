import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
  padded?: boolean;
};

/** The shared surface: a bordered panel on the themed background. */
export function Card({ children, className = "", padded = true }: CardProps) {
  return (
    <div
      className={`rounded-md border border-line bg-surface ${padded ? "px-3.5 py-3" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
