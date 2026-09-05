import {
  Body1,
  Caption1,
  Link,
  makeStyles,
  mergeClasses,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import type { ReactNode } from "react";

import { useEvidence } from "./evidence";
import type { Authorship } from "./evidence";
import type { CitedText, CitationId, WorkflowContext } from "./contracts";

/**
 * The one surface recipe for the whole app: white content plane on the warm
 * page, warm hairline border, sharp corners. `interactive` adds hover physics;
 * `ruled` swaps the box for a hairline top rule so list rows read as an index,
 * not a wall of cards.
 */
export const useSurfaceStyles = makeStyles({
  surface: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
    ...shorthands.padding(tokens.spacingVerticalL, tokens.spacingHorizontalL),
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  interactive: {
    cursor: "pointer",
    textAlign: "start",
    transitionProperty: "border-color, background-color, box-shadow",
    transitionDuration: "180ms",
    transitionTimingFunction: "ease",
    ":hover": {
      ...shorthands.borderColor(tokens.colorBrandStroke1),
      boxShadow: tokens.shadow4,
    },
  },
  ruled: {
    ...shorthands.border("none"),
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingInline: 0,
    paddingBlock: tokens.spacingVerticalM,
    backgroundColor: "transparent",
  },
});

const useEyebrowStyles = makeStyles({
  root: {
    display: "block",
    color: tokens.colorNeutralForeground3,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontSize: tokens.fontSizeBase200,
  },
});

/** Wide-tracked uppercase section label. Use sparingly; the headline usually
 * carries the section on its own. */
export function Eyebrow({
  children,
  id,
  className,
}: {
  children: ReactNode;
  id?: string;
  className?: string;
}) {
  const styles = useEyebrowStyles();
  return (
    <Caption1
      as="span"
      id={id}
      className={mergeClasses(styles.root, className)}
    >
      {children}
    </Caption1>
  );
}

const useStyles = makeStyles({
  list: {
    display: "flex",
    flexDirection: "column",
    ...shorthands.margin(0),
    ...shorthands.padding(0),
    listStyleType: "none",
  },
  item: {
    display: "flex",
    minWidth: 0,
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
  },
  itemActions: {
    display: "flex",
    justifyContent: "flex-start",
  },
  prose: {
    maxWidth: "65ch",
  },
});

export function WhyButton({
  citations,
  clientId,
  claim,
  authorship,
  children = "Why?",
}: {
  citations: CitationId[];
  clientId: string;
  /** The generated line this button sits under, shown at the top of the drawer. */
  claim?: string;
  authorship?: Authorship;
  children?: string;
}) {
  const { openEvidence } = useEvidence();

  return (
    <Link
      as="button"
      type="button"
      onClick={() => openEvidence({ citations, clientId, claim, authorship })}
    >
      {children}
    </Link>
  );
}

export function CitedList({
  items,
  clientId,
  authorship,
  evidenceContext,
}: {
  items: CitedText[];
  clientId: string;
  authorship?: Authorship;
  evidenceContext?: string;
}) {
  const styles = useStyles();
  const surfaces = useSurfaceStyles();

  return (
    <ul className={styles.list}>
      {items.map((item, index) => (
        <li
          className={mergeClasses(
            styles.item,
            surfaces.surface,
            surfaces.ruled,
          )}
          key={`${item.text}:${index}`}
        >
          <Body1 className={styles.prose}>{item.text}</Body1>
          <div className={styles.itemActions}>
            <WhyButton
              citations={item.citations}
              clientId={clientId}
              claim={[evidenceContext, item.text].filter(Boolean).join(" ")}
              authorship={authorship}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function WorkflowList({
  items,
  clientId,
  clientName,
  authorship,
}: {
  items: WorkflowContext[];
  clientId: string;
  clientName: string;
  authorship: Authorship;
}) {
  const styles = useStyles();
  const surfaces = useSurfaceStyles();

  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li
          className={mergeClasses(
            styles.item,
            surfaces.surface,
            surfaces.ruled,
          )}
          key={`${item.system}:${item.status}`}
        >
          <div>
            <Eyebrow>{item.system}</Eyebrow>
            <Body1>{item.status}</Body1>
          </div>
          {item.citations.length > 0 && (
            <div className={styles.itemActions}>
              <WhyButton
                citations={item.citations}
                clientId={clientId}
                claim={`${clientName} · ${item.system}: ${item.status}`}
                authorship={authorship}
              />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
