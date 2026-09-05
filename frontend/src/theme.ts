import {
  createLightTheme,
  type BrandVariants,
  type Theme,
} from "@fluentui/react-components";

/**
 * Aurelis royal navy, anchored at brand80 = #141E55 (the primary CTA color).
 * In a Fluent light theme: colorBrandBackground = 80, hover = 70, pressed = 60,
 * links and brand foregrounds sit around 70-80, and pale selection washes come
 * from the 140-160 tints.
 */
const aurelisNavy: BrandVariants = {
  10: "#050815",
  20: "#0A0D26",
  30: "#0D1134",
  40: "#0F143E",
  50: "#111746",
  60: "#12194C",
  70: "#131C51",
  80: "#141E55",
  90: "#2B3568",
  100: "#424C7B",
  110: "#59628E",
  120: "#7079A1",
  130: "#8891B4",
  140: "#A3ABC7",
  150: "#C0C5DB",
  160: "#DFE2EE",
};

const base = createLightTheme(aurelisNavy);

export const aurelisTheme: Theme = {
  ...base,

  // Shape: sharp corners everywhere; the 2px XLarge keeps drawers from feeling
  // like raw rectangles without reintroducing rounded chrome.
  borderRadiusNone: "0",
  borderRadiusSmall: "0",
  borderRadiusMedium: "0",
  borderRadiusLarge: "0",
  borderRadiusXLarge: "2px",

  // Typography: light geometric sans; soften Fluent's 600-weight headings.
  fontFamilyBase:
    "'Jost Variable', Jost, 'Avenir Next', 'Segoe UI', system-ui, sans-serif",
  fontWeightSemibold: 500,
  fontWeightBold: 600,

  // Neutrals: warm off-white chrome, pure white content surfaces, warm
  // hairlines, near-black ink.
  colorNeutralBackground1: "#FFFFFF",
  colorNeutralBackground2: "#F7F7F4",
  colorNeutralBackground3: "#F4F4F2",
  colorNeutralBackground4: "#ECECE7",
  colorNeutralBackground1Hover: "#F7F7F4",
  colorNeutralBackground3Hover: "#ECECE7",
  colorNeutralStroke1: "#D6D5CE",
  colorNeutralStroke2: "#E4E3DC",
  colorNeutralStroke3: "#EEEDE7",
  colorNeutralForeground1: "#1B1B1F",
  colorNeutralForeground2: "#3C3D45",
  colorNeutralForeground3: "#6A6B75",

  // Muted, desaturated status palette. Danger: deep red. Warning: warm amber.
  // Success: muted green. These drive Badge, MessageBar, and status tokens.
  colorPaletteRedBackground1: "#F9EFED",
  colorPaletteRedBackground3: "#7A241D",
  colorPaletteRedForeground1: "#6E1F19",
  colorPaletteRedForeground3: "#7A241D",
  colorPaletteRedBorder1: "#E5CBC7",
  colorPaletteDarkOrangeBackground1: "#F9F2E7",
  colorPaletteDarkOrangeBackground3: "#8A5B12",
  colorPaletteDarkOrangeForeground1: "#7A500F",
  colorPaletteDarkOrangeForeground3: "#8A5B12",
  colorPaletteYellowBackground1: "#F9F4E3",
  colorPaletteYellowBackground3: "#8A5B12",
  colorPaletteYellowForeground1: "#7A500F",
  colorPaletteGreenBackground1: "#EEF3EE",
  colorPaletteGreenBackground3: "#2F5E40",
  colorPaletteGreenForeground1: "#2A5439",
  colorPaletteGreenForeground3: "#2F5E40",
  colorStatusDangerBackground1: "#F9EFED",
  colorStatusDangerBorder1: "#E5CBC7",
  colorStatusDangerForeground1: "#6E1F19",
  colorStatusDangerBackground3: "#7A241D",
  colorStatusWarningBackground1: "#F9F2E7",
  colorStatusWarningBorder1: "#E9D8B8",
  colorStatusWarningForeground1: "#7A500F",
  colorStatusSuccessBackground1: "#EEF3EE",
  colorStatusSuccessBorder1: "#CBDCCE",
  colorStatusSuccessForeground1: "#2A5439",

  // Restrained elevation: hairlines do the work, shadows whisper.
  shadow2: "0 1px 2px rgba(20, 30, 85, 0.06)",
  shadow4: "0 1px 3px rgba(20, 30, 85, 0.08)",
  shadow8: "0 2px 8px rgba(20, 30, 85, 0.10)",
  shadow16: "0 4px 16px rgba(20, 30, 85, 0.12)",
  shadow28: "0 8px 28px rgba(20, 30, 85, 0.14)",
  shadow64: "0 12px 44px rgba(20, 30, 85, 0.16)",
};

/** Serif is reserved for the Aurelis wordmark; everything else is the sans. */
export const WORDMARK_FONT = "'Cormorant Garamond', Georgia, serif";
