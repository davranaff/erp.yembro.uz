/**
 * Серверные SVG-иконки. Простые, без зависимостей.
 */
import type { SVGProps } from "react";

const baseProps = {
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function ChickIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <ellipse cx="12" cy="14" rx="6" ry="5" />
      <circle cx="12" cy="8" r="3.5" />
      <circle cx="13" cy="7" r="0.6" fill="currentColor" />
      <path d="M15 9l1.5 0.4" />
      <path d="M9 18l-1 2M15 18l1 2" />
    </svg>
  );
}

export function EggIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <ellipse cx="12" cy="13" rx="6.5" ry="8.5" />
    </svg>
  );
}

export function FeatherIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
      <line x1="16" y1="8" x2="2" y2="22" />
      <line x1="17.5" y1="15" x2="9" y2="15" />
    </svg>
  );
}

export function GrainIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M12 22V8" />
      <path d="M12 8 a4 4 0 0 0 -4 -4 H6 v2 a4 4 0 0 0 4 4 H12" />
      <path d="M12 8 a4 4 0 0 1 4 -4 H18 v2 a4 4 0 0 1 -4 4 H12" />
      <path d="M12 13 a4 4 0 0 0 -4 -4 H6 v2 a4 4 0 0 0 4 4 H12" />
      <path d="M12 13 a4 4 0 0 1 4 -4 H18 v2 a4 4 0 0 1 -4 4 H12" />
      <path d="M12 18 a4 4 0 0 0 -4 -4 H6 v2 a4 4 0 0 0 4 4 H12" />
      <path d="M12 18 a4 4 0 0 1 4 -4 H18 v2 a4 4 0 0 1 -4 4 H12" />
    </svg>
  );
}

export function LeafIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19.2 2.96c1.4 9.3-3.4 15.5-8.2 17.04Z" />
      <path d="M2 22c1.5-3.5 4.5-7 7-9" />
    </svg>
  );
}

export function ShieldIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

export function TruckIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M14 18V6H1v11h2" />
      <path d="M14 8h4l3 3v6h-2" />
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="18" r="2" />
    </svg>
  );
}

export function FlaskIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M9 2v6L4 18a2 2 0 0 0 1.7 3h12.6a2 2 0 0 0 1.7-3L15 8V2" />
      <line x1="9" y1="2" x2="15" y2="2" />
      <line x1="7.5" y1="14" x2="16.5" y2="14" />
    </svg>
  );
}

export function ChartIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M3 3v18h18" />
      <path d="M7 14l4-4 4 3 5-7" />
    </svg>
  );
}

export function StarIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} fill="currentColor" stroke="none" {...p}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

export function ArrowRightIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function CheckIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function PhoneIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.86 19.86 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  );
}

export function MailIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}

export function GlobeIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...p}>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

const DIRECTION_ICONS = {
  broiler: ChickIcon,
  layer: EggIcon,
  parent: FeatherIcon,
  universal: GrainIcon,
} as const;

export function DirectionIcon({
  direction,
  ...rest
}: SVGProps<SVGSVGElement> & { direction: string }) {
  const Icon =
    DIRECTION_ICONS[direction as keyof typeof DIRECTION_ICONS] ?? GrainIcon;
  return <Icon {...rest} />;
}
