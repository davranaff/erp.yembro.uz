import clsx from "clsx";
import type { CSSProperties, ReactNode } from "react";

export function Container({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={clsx("container", className)}>{children}</div>;
}

export function Section({
  children,
  className,
  id,
  style,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
  style?: CSSProperties;
}) {
  return (
    <section id={id} className={clsx("section", className)} style={style}>
      <div className="container">{children}</div>
    </section>
  );
}
