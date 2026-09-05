/**
 * DEMO OVERLAY. Hardcoded presentation data for the two featured contrast
 * personas. Every number below is hand-derived from the frozen preview fixture
 * (frontend/preview/dashboard.json, as of 2026-08-26) and reconciles with the
 * fixture's own facts; citation ids point at real evidence rows so the "Why?"
 * drawer keeps working. The other 18 clients have no persona and render the
 * standard experience.
 */

export interface PersonaAllocationSlice {
  label: string;
  pct: number;
  detail: string;
  citations: string[];
}

export interface PersonaLifeEvent {
  happened: string;
  nextStep: string;
  citations: string[];
}

export interface PersonaDelta {
  label: string;
  scaledPct: number;
  display: string;
  citations: string[];
}

export interface PersonaSlide {
  kicker: string;
  title: string;
  lines: string[];
}

export interface Persona {
  clientId: string;
  stance: string;
  stanceDetail: string;
  hook: string;
  totalDisplay: string;
  allocation: PersonaAllocationSlice[];
  performance: PersonaDelta[];
  lifeEvents: PersonaLifeEvent[];
  keywords: string[];
  pitch: PersonaSlide[];
}

/** Fixed class order shared by both personas so the donuts compare directly. */
const RAVI: Persona = {
  clientId: "CL-0002",
  stance: "Aggressive growth",
  stanceDetail: "Risk tolerance 8 of 10 · pre-liquidity founder",
  hook: "Founder exit expected Q4 2026. 68% sits in one unlisted position.",
  totalDisplay: "USD 46.7m",
  allocation: [
    {
      label: "Equity",
      pct: 24,
      detail: "USD 11.0m",
      citations: [
        "holdings:2026-08-26:PF-0003:SYN-EQ-0003",
        "holdings:2026-08-26:PF-0003:SYN-ST-0102",
        "holdings:2026-08-26:PF-0003:SYN-ST-0103",
        "holdings:2026-08-26:PF-0003:SYN-EQ-0022",
        "holdings:2026-08-26:PF-0003:SYN-EQ-0001",
      ],
    },
    {
      label: "Fixed income",
      pct: 3,
      detail: "USD 1.2m",
      citations: ["holdings:2026-08-26:PF-0003:SYN-FI-0208"],
    },
    {
      label: "Alternatives",
      pct: 68,
      detail: "USD 31.9m",
      citations: ["holdings:2026-08-26:PF-0004:SYN-AL-0308"],
    },
    {
      label: "Structured",
      pct: 3,
      detail: "USD 1.6m",
      citations: ["holdings:2026-08-26:PF-0003:SYN-SP-0502"],
    },
    {
      label: "Cash",
      pct: 2,
      detail: "USD 1.0m",
      citations: ["holdings:2026-08-26:PF-0003:SYN-CA-0601"],
    },
  ],
  performance: [
    {
      label: "Helios ELN 11% 6M (new)",
      scaledPct: 100,
      display: "+1,572,000",
      citations: ["holdings:2026-08-26:PF-0003:SYN-SP-0502"],
    },
    {
      label: "US Technology Leaders Fund",
      scaledPct: 30,
      display: "+475,800",
      citations: [
        "holdings:2026-08-26:PF-0003:SYN-EQ-0003",
        "holdings:2025-12-31:PF-0003:SYN-EQ-0003",
      ],
    },
    {
      label: "Helios Cloud Systems Inc",
      scaledPct: 21,
      display: "+322,400",
      citations: [
        "holdings:2026-08-26:PF-0003:SYN-ST-0103",
        "holdings:2025-12-31:PF-0003:SYN-ST-0103",
      ],
    },
  ],
  lifeEvents: [
    {
      happened: "Secondary sale of founder shares expected Q4 2026.",
      nextStep: "Plan post-exit diversification now, before the cash lands.",
      citations: ["rm_notes:N-003", "clients:CL-0002"],
    },
    {
      happened: "Drew USD 1.7m more against volatile tech collateral.",
      nextStep: "Review the Lombard line: LTV is 1.3pp from a margin call.",
      citations: ["rm_notes:N-004", "CL-0002:fact:facility"],
    },
    {
      happened: "Family trust funding of USD 2.0m starts in 67 days.",
      nextStep: "Open the trust and protection conversation this meeting.",
      citations: ["planned_cash_needs:CN-003", "CL-0002:fact:deadline"],
    },
  ],
  keywords: [
    "secondary",
    "collateral",
    "tech",
    "Lombard",
    "utilisation",
    "difficult",
  ],
  pitch: [
    {
      kicker: "Aurelis · prepared for your meeting",
      title: "Ravi Chandrasekaran",
      lines: [
        "Aggressive growth · risk tolerance 8 of 10",
        "USD 46.7m across two portfolios",
        "Pre-liquidity: founder exit expected Q4 2026",
      ],
    },
    {
      kicker: "Where the money is",
      title: "68% in one unlisted position",
      lines: [
        "Alternatives 68% · Equity 24% · rest 8%",
        "Alternatives mandate maximum: 30%",
        "Concentration and the exit are the same conversation",
      ],
    },
    {
      kicker: "The pressure point",
      title: "1.3pp from a margin call",
      lines: [
        "Facility LTV 73.7% against a 75% trigger",
        "Collateral is the same tech complex he refuses to sell",
        "A 5% drawdown forces the sale he wants to avoid",
      ],
    },
    {
      kicker: "Life, not just money",
      title: "The trust needs funding in 67 days",
      lines: [
        "USD 2.0m family trust establishment by November",
        "Cover it from cash, not from collateralised positions",
        "Protection review belongs in the same conversation",
      ],
    },
    {
      kicker: "Recommended next steps",
      title: "Three asks for Monday",
      lines: [
        "Agree a de-risking path to the 30% alternatives cap",
        "Reduce facility utilisation before Q4 volatility",
        "Ring-fence the USD 2.0m trust funding now",
      ],
    },
  ],
};

const MARGARETHE: Persona = {
  clientId: "CL-0003",
  stance: "Conservative income",
  stanceDetail: "Risk tolerance 2 of 10 · recently inherited",
  hook: "Wants “safe and boring”. Holds 71% equity against a 30% cap.",
  totalDisplay: "EUR 20.3m",
  allocation: [
    {
      label: "Equity",
      pct: 71,
      detail: "EUR 14.5m",
      citations: [
        "holdings:2026-08-26:PF-0005:SYN-EQ-0010",
        "holdings:2026-08-26:PF-0005:SYN-ST-0107",
        "holdings:2026-08-26:PF-0005:SYN-EQ-0004",
        "holdings:2026-08-26:PF-0005:SYN-EQ-0003",
      ],
    },
    {
      label: "Fixed income",
      pct: 9,
      detail: "EUR 1.9m",
      citations: ["holdings:2026-08-26:PF-0005:SYN-FI-0209"],
    },
    {
      label: "Alternatives",
      pct: 6,
      detail: "EUR 1.3m",
      citations: ["holdings:2026-08-26:PF-0005:SYN-AL-0304"],
    },
    {
      label: "Structured",
      pct: 6,
      detail: "EUR 1.1m",
      citations: ["holdings:2026-08-26:PF-0005:SYN-SP-0506"],
    },
    {
      label: "Cash",
      pct: 8,
      detail: "EUR 1.6m",
      citations: [
        "holdings:2026-08-26:PF-0005:SYN-CA-0604",
        "holdings:2026-08-26:PF-0005:SYN-CA-0605",
      ],
    },
  ],
  performance: [
    {
      label: "Global Luxury and Consumer Brands",
      scaledPct: -100,
      display: "-532,400",
      citations: [
        "holdings:2026-08-26:PF-0005:SYN-EQ-0010",
        "holdings:2025-12-31:PF-0005:SYN-EQ-0010",
      ],
    },
    {
      label: "US Technology Leaders Fund",
      scaledPct: 75,
      display: "+400,589",
      citations: [
        "holdings:2026-08-26:PF-0005:SYN-EQ-0003",
        "holdings:2025-12-31:PF-0005:SYN-EQ-0003",
      ],
    },
    {
      label: "EUR Investment Grade Bond Fund",
      scaledPct: -26,
      display: "-138,000",
      citations: [
        "holdings:2026-08-26:PF-0005:SYN-FI-0209",
        "holdings:2025-12-31:PF-0005:SYN-FI-0209",
      ],
    },
  ],
  lifeEvents: [
    {
      happened: "Inherited the portfolio; her husband handled all of it.",
      nextStep:
        "De-risk to the mandate. Move toward income funds she understands.",
      citations: ["rm_notes:N-005", "CL-0003:fact:mandate-gap"],
    },
    {
      happened: "EUR 3.4m inheritance tax falls due in 36 days.",
      nextStep:
        "Secure the liquidity now, from cash and bond sales, not equity in a dip.",
      citations: ["planned_cash_needs:CN-004", "CL-0003:fact:deadline"],
    },
    {
      happened: "Asked for “something safe and boring” after market news.",
      nextStep: "Open the estate and insurance review for the transition.",
      citations: ["rm_notes:N-006"],
    },
  ],
  keywords: ["risk", "husband", "inheritance", "tax", "safe", "conservative"],
  pitch: [
    {
      kicker: "Aurelis · prepared for your meeting",
      title: "Margarethe Voss-Brenner",
      lines: [
        "Conservative income · risk tolerance 2 of 10",
        "EUR 20.3m, recently inherited",
        "Goal: understand, de-risk, secure stable income",
      ],
    },
    {
      kicker: "Where the money is",
      title: "71% equity in a conservative mandate",
      lines: [
        "Equity 71% against a 30% maximum",
        "She says: “I have never taken a risk with money”",
        "The portfolio she inherited disagrees",
      ],
    },
    {
      kicker: "The deadline",
      title: "EUR 3.4m tax due in 36 days",
      lines: [
        "German inheritance tax instalment, confirmed",
        "Fund it from cash and bonds, not equity sales in a dip",
        "Liquidity coverage today: 5.3x",
      ],
    },
    {
      kicker: "Life, not just money",
      title: "Safe, boring, and protected",
      lines: [
        "Shift toward income and dividend funds she understands",
        "Estate and insurance review for the transition",
        "Report in German, decisions at her pace",
      ],
    },
    {
      kicker: "Recommended next steps",
      title: "Three asks for Monday",
      lines: [
        "Agree the de-risking path to the 30% equity cap",
        "Ring-fence EUR 3.4m for the tax instalment",
        "Book the estate and insurance conversation",
      ],
    },
  ],
};

const PERSONAS: Record<string, Persona> = {
  [RAVI.clientId]: RAVI,
  [MARGARETHE.clientId]: MARGARETHE,
};

export function getPersona(clientId: string): Persona | undefined {
  return PERSONAS[clientId];
}

/** The two featured contrast personas, aggressive first. */
export const FEATURED_PERSONAS: Persona[] = [RAVI, MARGARETHE];
