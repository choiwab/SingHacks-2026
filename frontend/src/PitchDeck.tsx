import {
  Body1,
  Button,
  Caption1,
  Link,
  makeStyles,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import type { MondayBriefProjection } from "./contracts";
import { getPersona } from "./demo/personas";
import { Eyebrow } from "./shared";
import { WORDMARK_FONT } from "./theme";

const useStyles = makeStyles({
  screen: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100dvh",
  },
  kickerBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalL,
    paddingBlock: tokens.spacingVerticalM,
    paddingInline: tokens.spacingHorizontalXXL,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  slide: {
    flexGrow: 1,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    rowGap: tokens.spacingVerticalL,
    paddingBlock: tokens.spacingVerticalXXXL,
    paddingInline: tokens.spacingHorizontalXXL,
  },
  slideLight: {
    backgroundColor: tokens.colorNeutralBackground1,
  },
  slideDark: {
    backgroundColor: "#141E55",
  },
  title: {
    fontSize: tokens.fontSizeHero900,
    lineHeight: tokens.lineHeightHero900,
    fontWeight: 300,
    letterSpacing: "-0.01em",
    maxWidth: "18em",
    color: tokens.colorNeutralForeground1,
  },
  titleDark: {
    color: "#FFFFFF",
  },
  kickerDark: {
    color: "#C0C5DB",
  },
  lines: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
    margin: 0,
    padding: 0,
    listStyleType: "none",
  },
  line: {
    maxWidth: "48ch",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingTop: tokens.spacingVerticalS,
  },
  lineDark: {
    borderTopColor: "#2B3568",
    color: "#DFE2EE",
  },
  controls: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalL,
    paddingBlock: tokens.spacingVerticalM,
    paddingInline: tokens.spacingHorizontalXXL,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  controlGroup: {
    display: "flex",
    columnGap: tokens.spacingHorizontalS,
  },
  counter: {
    fontVariantNumeric: "tabular-nums",
  },
  wordmark: {
    fontFamily: WORDMARK_FONT,
    fontSize: "18px",
    color: tokens.colorBrandForeground1,
  },
});

/**
 * The AI-prepared pitch deck for a featured persona: full-viewport slides with
 * keyboard navigation. Cover and closing slides run navy; content slides stay
 * on the light surface (a deliberate cover treatment, not per-section theme
 * flips).
 */
export function PitchDeck({
  projection,
}: {
  projection: MondayBriefProjection;
}) {
  const styles = useStyles();
  const navigate = useNavigate();
  const { clientId = "" } = useParams();
  const persona = getPersona(clientId);
  const preRead = projection.pre_reads[clientId];
  const [index, setIndex] = useState(0);

  const slideCount = persona?.pitch.length ?? 0;

  useEffect(() => {
    if (!persona) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight")
        setIndex((i) => Math.min(i + 1, slideCount - 1));
      else if (event.key === "ArrowLeft") setIndex((i) => Math.max(i - 1, 0));
      else if (event.key === "Escape")
        navigate(`/clients/${clientId}/pre-read`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [persona, slideCount, clientId, navigate]);

  if (!persona || !preRead) {
    return (
      <Navigate
        to="/"
        replace
        state={{
          notice: `No pitch deck is prepared for ${clientId || "this client"}. Showing the dashboard.`,
        }}
      />
    );
  }

  const slide = persona.pitch[index];
  const dark = index === 0 || index === slideCount - 1;

  return (
    <section className={styles.screen} aria-labelledby="pitch-title">
      <div className={styles.kickerBar}>
        <Link
          as="button"
          type="button"
          onClick={() => navigate(`/clients/${clientId}/pre-read`)}
        >
          ← Meeting brief
        </Link>
        <span className={styles.wordmark}>Aurelis</span>
      </div>
      <div
        className={mergeClasses(
          styles.slide,
          dark ? styles.slideDark : styles.slideLight,
        )}
        role="group"
        aria-roledescription="slide"
        aria-label={`Slide ${index + 1} of ${slideCount}: ${slide.title}`}
      >
        <Eyebrow className={dark ? styles.kickerDark : undefined}>
          {slide.kicker}
        </Eyebrow>
        <h1
          id="pitch-title"
          className={mergeClasses(styles.title, dark && styles.titleDark)}
        >
          {slide.title}
        </h1>
        <ul className={styles.lines}>
          {slide.lines.map((line) => (
            <li
              key={line}
              className={mergeClasses(styles.line, dark && styles.lineDark)}
            >
              <Body1 as="span">{line}</Body1>
            </li>
          ))}
        </ul>
      </div>
      <div className={styles.controls}>
        <Caption1 className={styles.counter} role="status" aria-atomic="true">
          Slide {index + 1} of {slideCount}
        </Caption1>
        <div className={styles.controlGroup}>
          <Button
            disabledFocusable={index === 0}
            onClick={() => setIndex((i) => Math.max(i - 1, 0))}
          >
            Previous
          </Button>
          <Button
            appearance="primary"
            disabledFocusable={index === slideCount - 1}
            onClick={() => setIndex((i) => Math.min(i + 1, slideCount - 1))}
          >
            Next
          </Button>
        </div>
      </div>
    </section>
  );
}
