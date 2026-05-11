/**
 * Логотип Yembro в двух вариантах:
 * - <LogoMark /> — только знак (петух в арке) для тесных мест: header, favicon
 * - <LogoFull /> — полный lockup mark + текстом «YemBro» с тэглайном
 *
 * Используем нативный <img>, а не next/image: логотипы статичные и
 * относительно лёгкие (mark 36kb, full lockup 215kb), а оптимизатор
 * с заданными `width: auto` для пропорций даёт битую вёрстку на
 * широких изображениях вроде 2723×851.
 */

const MARK_RATIO = 851 / 499; // высота / ширина
const FULL_RATIO = 851 / 2723;

type LogoMarkProps = {
  size?: number;
  alt?: string;
  style?: React.CSSProperties;
  className?: string;
};

export function LogoMark({
  size = 36,
  alt = "Yembro",
  style,
  className,
}: LogoMarkProps) {
  const height = size;
  const width = Math.round(size / MARK_RATIO);
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/mark.png"
      alt={alt}
      width={width}
      height={height}
      decoding="async"
      style={{
        display: "block",
        width,
        height,
        objectFit: "contain",
        flexShrink: 0,
        ...style,
      }}
      className={className}
    />
  );
}

type LogoFullProps = {
  height?: number;
  alt?: string;
  style?: React.CSSProperties;
  className?: string;
};

export function LogoFull({
  height = 48,
  alt = "Yembro — Yuqori sifat, yuqori samaradorlik",
  style,
  className,
}: LogoFullProps) {
  const width = Math.round(height / FULL_RATIO);
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/logo.png"
      alt={alt}
      width={width}
      height={height}
      decoding="async"
      style={{
        display: "block",
        width,
        height,
        maxWidth: "100%",
        objectFit: "contain",
        flexShrink: 0,
        ...style,
      }}
      className={className}
    />
  );
}
