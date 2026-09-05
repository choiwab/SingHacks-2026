import { Caption1, makeStyles, tokens } from "@fluentui/react-components";

/**
 * Categorical chart palette, validated (CVD-safe adjacent pairs, lightness
 * band, chroma floor) against the light surface. Colors follow the entity in
 * fixed slot order; identity is never color-alone: every chart pairs color
 * with a legend and per-mark labels.
 */
export const CHART_SERIES = [
  "#3D57B8",
  "#C4571E",
  "#0D9B9B",
  "#C9A227",
  "#A45CA0",
] as const;

/** Polarity pair for gains/losses, shared with the status palette. */
const GAIN = "#2F5E40";
const LOSS = "#7A241D";

const useStyles = makeStyles({
  donutWrap: {
    display: "flex",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalXL,
    rowGap: tokens.spacingVerticalM,
    flexWrap: "wrap",
  },
  legend: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXS,
    listStyleType: "none",
    margin: 0,
    padding: 0,
  },
  legendRow: {
    display: "flex",
    alignItems: "baseline",
    columnGap: tokens.spacingHorizontalS,
  },
  swatch: {
    flexShrink: 0,
    inlineSize: "10px",
    blockSize: "10px",
    alignSelf: "center",
  },
  legendValue: {
    marginInlineStart: "auto",
    fontVariantNumeric: "tabular-nums",
    color: tokens.colorNeutralForeground2,
    paddingInlineStart: tokens.spacingHorizontalM,
  },
  legendLabel: {
    color: tokens.colorNeutralForeground1,
  },
  bars: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
  },
  barRow: {
    display: "grid",
    gridTemplateColumns: "minmax(8rem, 14rem) minmax(0, 1fr)",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalM,
  },
  barLabel: {
    color: tokens.colorNeutralForeground1,
    overflowWrap: "anywhere",
  },
  barTrack: {
    position: "relative",
    blockSize: "1.25rem",
  },
  zeroLine: {
    position: "absolute",
    insetBlockStart: 0,
    insetBlockEnd: 0,
    insetInlineStart: "50%",
    inlineSize: "1px",
    backgroundColor: tokens.colorNeutralStroke1,
  },
  bar: {
    position: "absolute",
    insetBlockStart: "50%",
    blockSize: "10px",
    transform: "translateY(-50%)",
  },
  barValue: {
    position: "absolute",
    insetBlockStart: "50%",
    transform: "translateY(-50%)",
    whiteSpace: "nowrap",
    fontSize: tokens.fontSizeBase200,
    fontVariantNumeric: "tabular-nums",
    color: tokens.colorNeutralForeground2,
  },
});

export interface DonutSlice {
  label: string;
  /** Percentage share, 0-100. Slices should sum to ~100. */
  pct: number;
  /** Formatted value shown in the legend beside the share. */
  detail?: string;
}

function arcPath(cx: number, cy: number, r: number, a0: number, a1: number) {
  const p = (a: number) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
}

/**
 * Part-of-whole donut. Ring marks with 2px surface gaps, a center label, and a
 * value legend; the accessible name carries the full text equivalent.
 */
export function DonutChart({
  slices,
  centerLabel,
  centerValue,
  title,
  size = 148,
}: {
  slices: DonutSlice[];
  centerLabel?: string;
  centerValue?: string;
  /** Text summary for assistive technology, e.g. "Allocation: Equities 62%, ...". */
  title: string;
  size?: number;
}) {
  const styles = useStyles();
  const r = size / 2 - 14;
  const c = size / 2;
  const total = slices.reduce((sum, slice) => sum + slice.pct, 0) || 1;
  const arcs = slices.reduce<
    { slice: DonutSlice; index: number; start: number; end: number }[]
  >((acc, slice, index) => {
    const start = acc.length > 0 ? acc[acc.length - 1].end : -Math.PI / 2;
    const sweep = (slice.pct / total) * Math.PI * 2;
    return [...acc, { slice, index, start, end: start + sweep }];
  }, []);

  return (
    <div className={styles.donutWrap}>
      <svg width={size} height={size} role="img" aria-label={title}>
        {arcs.map(({ slice, index, start, end }) => (
          <path
            key={slice.label}
            d={arcPath(c, c, r, start, Math.max(end, start + 0.02))}
            fill="none"
            stroke={CHART_SERIES[index % CHART_SERIES.length]}
            strokeWidth={22}
          >
            <title>{`${slice.label}: ${slice.pct}%`}</title>
          </path>
        ))}
        {/* 2px surface gaps between slices */}
        {arcs.map(({ slice, start }) => (
          <line
            key={`gap-${slice.label}`}
            x1={c + (r - 13) * Math.cos(start)}
            y1={c + (r - 13) * Math.sin(start)}
            x2={c + (r + 13) * Math.cos(start)}
            y2={c + (r + 13) * Math.sin(start)}
            stroke={tokens.colorNeutralBackground1}
            strokeWidth={2}
          />
        ))}
        {centerValue && (
          <text
            x={c}
            y={centerLabel ? c : c + 5}
            textAnchor="middle"
            fontSize="17"
            fontWeight="500"
            fill={tokens.colorNeutralForeground1}
          >
            {centerValue}
          </text>
        )}
        {centerLabel && (
          <text
            x={c}
            y={c + 16}
            textAnchor="middle"
            fontSize="10"
            fill={tokens.colorNeutralForeground3}
          >
            {centerLabel}
          </text>
        )}
      </svg>
      <ul className={styles.legend}>
        {slices.map((slice, index) => (
          <li className={styles.legendRow} key={slice.label}>
            <span
              className={styles.swatch}
              style={{
                backgroundColor: CHART_SERIES[index % CHART_SERIES.length],
              }}
              aria-hidden="true"
            />
            <Caption1 className={styles.legendLabel}>{slice.label}</Caption1>
            <Caption1 className={styles.legendValue}>
              {slice.pct}%{slice.detail ? ` · ${slice.detail}` : ""}
            </Caption1>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface DeltaItem {
  label: string;
  /** Signed change as a percentage of the larger magnitude in the set, -100..100. */
  scaledPct: number;
  /** Formatted signed value shown at the bar end, e.g. "+400,589". */
  display: string;
}

/**
 * Signed horizontal bars around a zero baseline: losses run left in the status
 * deep red, gains run right in the muted green. Every bar carries its label and
 * value; the accessible name carries the full text equivalent.
 */
export function DeltaBars({
  items,
  title,
}: {
  items: DeltaItem[];
  title: string;
}) {
  const styles = useStyles();

  return (
    <div className={styles.bars} role="img" aria-label={title}>
      {items.map((item) => {
        const gain = item.scaledPct >= 0;
        // Cap the sweep so the value label always fits inside the panel.
        const width = Math.min(Math.abs(item.scaledPct) * 0.32, 32);
        return (
          <div className={styles.barRow} key={item.label}>
            <Caption1 className={styles.barLabel}>{item.label}</Caption1>
            <div className={styles.barTrack}>
              <span className={styles.zeroLine} aria-hidden="true" />
              <span
                className={styles.bar}
                aria-hidden="true"
                style={{
                  backgroundColor: gain ? GAIN : LOSS,
                  insetInlineStart: gain ? "50%" : `${50 - width}%`,
                  inlineSize: `${Math.max(width, 0.5)}%`,
                }}
              />
              <span
                className={styles.barValue}
                aria-hidden="true"
                style={
                  gain
                    ? { insetInlineStart: `calc(${50 + width}% + 6px)` }
                    : { insetInlineEnd: `calc(${50 + width}% + 6px)` }
                }
              >
                {item.display}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
