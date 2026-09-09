import { getCollection, type CollectionEntry } from "astro:content";
import { docSections } from "../content.config";
import { href } from "./url";

export type Doc = CollectionEntry<"docs">;

/** All docs in sidebar order: by section, then by `order`, then by title. */
export async function orderedDocs(): Promise<Doc[]> {
  const docs = await getCollection("docs");
  const rank = (d: Doc) => docSections.indexOf(d.data.section);
  return docs.sort(
    (a, b) =>
      rank(a) - rank(b) || a.data.order - b.data.order || a.data.title.localeCompare(b.data.title),
  );
}

export const docHref = (doc: Doc) => href(`/docs/${doc.id}/`);

/** Sidebar groups: one per section that has pages. */
export function docNav(docs: Doc[]) {
  return docSections
    .map((section) => ({
      section,
      items: docs
        .filter((d) => d.data.section === section)
        .map((d) => ({ label: d.data.title, href: docHref(d) })),
    }))
    .filter((g) => g.items.length > 0);
}
