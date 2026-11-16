// Brand for the local viewer. It is compiled into the bundle (`make viewer`),
// so the committed bundle is always the Jitera build.
export interface Brand {
  name: string;
  homepage: string;
  // One-letter mark shown where upstream shows its logo.
  mark: string;
  // Upstream's Strix Cloud services: upsell CTAs, upgrade prompts, the email
  // report relay and the feedback relay. Off for Jitera: we don't offer them.
  upstreamCloud: boolean;
}

export const BRAND: Brand = {
  name: "Jitera",
  homepage: "https://jitera.com",
  mark: "J",
  upstreamCloud: false,
};
