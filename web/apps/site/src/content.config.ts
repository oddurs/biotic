import { glob } from "astro/loaders";
import { z } from "astro/zod";
import { defineCollection } from "astro:content";
import { fileURLToPath } from "node:url";
import { specimenLoader, specimenSchema } from "./lib/specimens";

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

const specimens = defineCollection({
  loader: specimenLoader(fileURLToPath(new URL("./content/specimens", import.meta.url))),
  schema: specimenSchema,
});

export const collections = { docs, specimens };
