import type { SVGProps } from "react";

// One sticker family: 2.5px ink outlines, round caps, brand-token fills.
const INK = "#202020";
const C = {
  mango: "#FFD76A",
  punch: "#F05A28",
  mint: "#BFECD4",
  lavender: "#DCCBFF",
  pink: "#FFD3D3",
  paper: "#FFFFFF",
  cream: "#FBEDD0",
};
const S = { stroke: INK, strokeWidth: 2.5, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export type StickerProps = SVGProps<SVGSVGElement> & { title?: string };

function Svg({ title, children, viewBox = "0 0 48 48", ...rest }: StickerProps) {
  return (
    <svg
      viewBox={viewBox}
      xmlns="http://www.w3.org/2000/svg"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}

export function NewspaperSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <rect x="7" y="10" width="34" height="28" rx="3" fill={C.paper} {...S} />
      <rect x="11" y="14" width="26" height="6" rx="1.5" fill={C.mango} {...S} />
      <path d="M11 25h11M11 30h11M11 35h7M27 25h10M27 30h10M27 35h10" fill="none" {...S} />
    </Svg>
  );
}

export function ScalesSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M24 9v29M15 40h18M9 14h30M9 14l-5 12M9 14l5 12M39 14l-5 12M39 14l5 12" fill="none" {...S} />
      <path d="M3 26h12a6 5 0 0 1-12 0zM33 26h12a6 5 0 0 1-12 0z" fill={C.lavender} {...S} />
      <circle cx="24" cy="8" r="3" fill={C.mango} {...S} />
    </Svg>
  );
}

export function CoinSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <circle cx="24" cy="24" r="17" fill={C.mango} {...S} />
      <circle cx="24" cy="24" r="12" fill="none" {...S} strokeWidth={1.5} />
      <path d="M18.5 17.5h11M18.5 22h11M19 17.5c7 0 7 9 0 9l8.5 7.5" fill="none" {...S} />
    </Svg>
  );
}

export function RocketSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M20 34c0 4 2 7 4 9 2-2 4-5 4-9" fill={C.punch} {...S} />
      <path d="M18 27l-6 7 7-1M30 27l6 7-7-1" fill={C.lavender} {...S} />
      <path d="M24 5c7 6 9 16 6 27H18c-3-11-1-21 6-27z" fill={C.mint} {...S} />
      <circle cx="24" cy="18" r="3.5" fill={C.paper} {...S} />
    </Svg>
  );
}

export function GlobeSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <circle cx="24" cy="24" r="17" fill={C.mint} {...S} />
      <ellipse cx="24" cy="24" rx="7" ry="17" fill="none" {...S} />
      <path d="M8 18.5h32M8 29.5h32" fill="none" {...S} />
    </Svg>
  );
}

export function LeafSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M9 39C7 20 19 8 41 8c0 21-12 33-32 31z" fill={C.mint} {...S} />
      <path d="M9 39L31 17M18 30l-1-8M24 24l7 1" fill="none" {...S} />
    </Svg>
  );
}

export function TrophySticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M15 11H9c0 6 3 9 7 9M33 11h6c0 6-3 9-7 9" fill="none" {...S} />
      <path d="M15 7h18v9a9 9 0 0 1-18 0V7z" fill={C.mango} {...S} />
      <path d="M24 25v6M17 41h14l-2-9H19z" fill={C.punch} {...S} />
    </Svg>
  );
}

export function MedalSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M13 5h8l6 13h-8zM35 5h-8l-6 13h8z" fill={C.punch} {...S} />
      <circle cx="24" cy="30" r="11" fill={C.mango} {...S} />
      <path
        d="M24 24.5l1.9 3.8 4.2.6-3 3 .7 4.2-3.8-2-3.8 2 .7-4.2-3-3 4.2-.6z"
        fill={C.paper}
        {...S}
        strokeWidth={1.5}
      />
    </Svg>
  );
}

export function StarSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path
        d="M24 5l5.6 11.4 12.6 1.8-9.1 8.8 2.2 12.5L24 33.6l-11.3 5.9 2.2-12.5-9.1-8.8 12.6-1.8z"
        fill={C.mango}
        {...S}
      />
    </Svg>
  );
}

export function BulbSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M24 5a12 12 0 0 0-7 21.8c1.4 1 2 2.4 2 4.2h10c0-1.8.6-3.2 2-4.2A12 12 0 0 0 24 5z" fill={C.mango} {...S} />
      <path d="M19 36h10M20.5 41h7M21 22l3-5 3 5" fill="none" {...S} />
    </Svg>
  );
}

export function PinSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M24 24v18" fill="none" {...S} />
      <circle cx="24" cy="15" r="10" fill={C.punch} {...S} />
      <circle cx="20.5" cy="11.5" r="2.5" fill={C.paper} />
    </Svg>
  );
}

export function PencilSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M9 39l4-12L32 8l8 8-19 19z" fill={C.mango} {...S} />
      <path d="M9 39l4-12 8 8z" fill={C.cream} {...S} />
      <path d="M32 8l3-3 8 8-3 3z" fill={C.pink} {...S} />
      <path d="M28 12l8 8" fill="none" {...S} />
    </Svg>
  );
}

export function SparkleSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M22 4c1.6 9.5 4.3 13 13.5 14.5C26.3 20 23.6 23.6 22 33c-1.6-9.4-4.3-13-13.5-14.5C17.7 17 20.4 13.5 22 4z" fill={C.lavender} {...S} />
      <path d="M38 29c.6 3.6 1.7 4.7 5.2 5.3-3.5.6-4.6 1.7-5.2 5.3-.6-3.6-1.7-4.7-5.2-5.3 3.5-.6 4.6-1.7 5.2-5.3z" fill={C.mango} {...S} strokeWidth={2} />
    </Svg>
  );
}

export function FlameSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <path d="M24 4c2 8 12 12 12 25a12 12 0 0 1-24 0c0-6 3-9 5-12 1 4 3 5 4 5-1-7 1-12 3-18z" fill={C.punch} {...S} />
      <path d="M24 30c2.2 2 4.2 4 4.2 7.2a4.2 4.2 0 0 1-8.4 0c0-3.2 2-5.2 4.2-7.2z" fill={C.mango} {...S} strokeWidth={2} />
    </Svg>
  );
}

export function NotebookSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <rect x="11" y="6" width="29" height="36" rx="3" fill={C.lavender} {...S} />
      <path d="M11 13H7M11 21H7M11 29H7M11 37H7M18 15h15M18 21h15M18 27h9" fill="none" {...S} />
    </Svg>
  );
}

export function CardsSticker(p: StickerProps) {
  return (
    <Svg {...p}>
      <rect x="6" y="12" width="26" height="30" rx="3" fill={C.pink} {...S} transform="rotate(-8 19 27)" />
      <rect x="16" y="7" width="26" height="30" rx="3" fill={C.mint} {...S} />
      <path d="M23 18h12M23 24h8" fill="none" {...S} />
    </Svg>
  );
}

export function ArrowDoodle(p: StickerProps) {
  return (
    <Svg viewBox="0 0 96 48" {...p}>
      <path d="M4 36c18 10 42 8 57-6 6-5 10-12 12-19" fill="none" {...S} />
      <path d="M62 12l11-2 3 11" fill="none" {...S} />
    </Svg>
  );
}

export function Stamp({ label, color = "#B83A12", className }: { label: string; color?: string; className?: string }) {
  return (
    <svg viewBox="0 0 72 72" className={className} aria-hidden="true" focusable="false">
      <circle cx="36" cy="36" r="31" fill="none" stroke={color} strokeWidth="3" strokeDasharray="5 3" />
      <circle cx="36" cy="36" r="24" fill="none" stroke={color} strokeWidth="2" />
      <text
        x="36"
        y="40"
        textAnchor="middle"
        fontSize={label.length > 7 ? 9 : 11}
        fontWeight="800"
        letterSpacing="1"
        fill={color}
        fontFamily="Space Grotesk Variable, Space Grotesk, sans-serif"
      >
        {label}
      </text>
    </svg>
  );
}

export type Mood = "happy" | "wow" | "oops" | "think" | "sleepy";

/** Bhaar-Bhai: a Bengali clay tea cup (bhaar) with a running commentary. */
export function Mascot({ mood = "happy", title, steam = true, ...rest }: StickerProps & { mood?: Mood; steam?: boolean }) {
  const eyeY = mood === "think" ? 75 : 78;
  return (
    <Svg viewBox="0 0 120 120" title={title} {...rest}>
      {steam ? (
        <g className="motion-safe:animate-steam" fill="none" {...S}>
          <path d="M47 33c-5-6 5-10 0-17" />
          <path d="M60 30c-5-6 5-10 0-17" />
          <path d="M73 33c-5-6 5-10 0-17" />
        </g>
      ) : null}
      <path d="M24 46h72l-9 54a8 8 0 0 1-8 7H41a8 8 0 0 1-8-7z" fill={C.punch} {...S} />
      <path d="M26.4 59h67.2l-1.3 8H27.7z" fill={C.mango} {...S} strokeWidth={2} />
      <ellipse cx="60" cy="46" rx="36" ry="9" fill={C.cream} {...S} />
      <ellipse cx="60" cy="46.5" rx="27" ry="5" fill={C.mango} stroke="none" />
      {mood === "sleepy" ? (
        <path d="M44 78h10M66 78h10" fill="none" {...S} />
      ) : (
        <>
          <ellipse cx="49" cy={eyeY} rx="3.2" ry="4.2" fill={INK} />
          <ellipse cx="71" cy={eyeY} rx="3.2" ry="4.2" fill={INK} />
          <circle cx="50.2" cy={eyeY - 1.6} r="1.1" fill={C.paper} />
          <circle cx="72.2" cy={eyeY - 1.6} r="1.1" fill={C.paper} />
        </>
      )}
      <ellipse cx="41" cy="88" rx="5" ry="3" fill={C.pink} />
      <ellipse cx="79" cy="88" rx="5" ry="3" fill={C.pink} />
      {mood === "happy" && <path d="M52 87c4 6 12 6 16 0" fill="none" {...S} />}
      {mood === "wow" && <ellipse cx="60" cy="90" rx="4.5" ry="5.5" fill={INK} />}
      {mood === "oops" && (
        <>
          <path d="M51 92c3-3 6 0 9-3s6 0 9-3" fill="none" {...S} />
          <path d="M89 63c3.5 4.5 3.5 8 0 9-3.5-1-3.5-4.5 0-9z" fill={C.mint} {...S} strokeWidth={2} />
        </>
      )}
      {mood === "think" && <path d="M55 90h10" fill="none" {...S} />}
      {mood === "sleepy" && <path d="M55 90c3 2 7 2 10 0" fill="none" {...S} />}
    </Svg>
  );
}
