import {
  Body1,
  Caption1,
  Link,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";

import { useEvidence } from "./evidence";
import type { Authorship } from "./evidence";
import type { CitedText, CitationId, WorkflowContext } from "./contracts";

const useStyles = makeStyles({
  list: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
    alignItems: "start",
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalM,
    ...shorthands.margin(0),
    ...shorthands.padding(0),
    listStyleType: "none",
  },
  item: {
    display: "flex",
    minWidth: 0,
    flexDirection: "column",
    justifyContent: "space-between",
    rowGap: tokens.spacingVerticalS,
    ...shorthands.padding(tokens.spacingVerticalM, tokens.spacingHorizontalM),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  itemActions: {
    display: "flex",
    justifyContent: "flex-start",
  },
  system: {
    display: "block",
    color: tokens.colorNeutralForeground3,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
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
}: {
  items: CitedText[];
  clientId: string;
  authorship?: Authorship;
}) {
  const styles = useStyles();

  return (
    <ul className={styles.list}>
      {items.map((item, index) => (
        <li className={styles.item} key={`${item.text}:${index}`}>
          <Body1>{item.text}</Body1>
          <div className={styles.itemActions}>
            <WhyButton
              citations={item.citations}
              clientId={clientId}
              claim={item.text}
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
}: {
  items: WorkflowContext[];
  clientId: string;
}) {
  const styles = useStyles();

  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li className={styles.item} key={`${item.system}:${item.status}`}>
          <div>
            <Caption1 className={styles.system}>{item.system}</Caption1>
            <Body1>{item.status}</Body1>
          </div>
          {item.citations.length > 0 && (
            <div className={styles.itemActions}>
              <WhyButton citations={item.citations} clientId={clientId} />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
