import { glob } from "astro/loaders";
import { z } from "astro/zod";
import { defineCollection } from "astro:content";

// Documentation. Sections order the sidebar; `order` orders pages within a section.
export const docSections = ["Start", "The instrument", "Reference", "Contributing"] as const;

const docs = defineCollection({
  loader: glob({ base: "./src/content/docs", pattern: "**/*.mdx" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    section: z.enum(docSections),
    order: z.number().int().nonnegative(),
    // Set by generators; pages with a generator are not edited by hand.
    generated: z.string().optional(),
  }),
});

export const collections = { docs };
