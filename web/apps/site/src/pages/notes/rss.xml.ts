import rss from "@astrojs/rss";
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { site } from "../../../site.config";
import { href } from "../../lib/url";

export const GET: APIRoute = async (context) => {
  const notes = (await getCollection("notes")).sort(
    (a, b) => b.data.date.getTime() - a.data.date.getTime(),
  );
  return rss({
    title: `${site.name} field notes`,
    description: site.description,
    site: context.site ?? site.url,
    items: notes.map((n) => ({
      title: n.data.title,
      description: n.data.description,
      pubDate: n.data.date,
      link: href(`/notes/${n.id}/`),
    })),
  });
};
