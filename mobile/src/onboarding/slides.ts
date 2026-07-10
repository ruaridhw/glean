export const ONBOARDING_SLIDES = [
  {
    body: "Snap a photo of your receipt and Glean turns it into pantry items you can review.",
    image: require("../../assets/onboarding/scan.png"),
    key: "scan",
    title: "Stock your pantry from a receipt",
  },
  {
    body: "Get weekly dinner ideas that use your pantry first and remember recipes you save.",
    image: require("../../assets/onboarding/plan.png"),
    key: "plan",
    title: "Plan meals around what you have",
  },
  {
    body: "When a meal needs something missing, Glean adds it to your shopping list.",
    image: require("../../assets/onboarding/shop.png"),
    key: "shop",
    title: "Shop only for the gaps",
  },
] as const;
