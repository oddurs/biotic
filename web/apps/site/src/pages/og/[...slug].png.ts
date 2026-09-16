import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { ogImage } from "../../lib/og";
import { site } from "../../../site.config";

// One image per page that has a title of its own, plus a default at /og/default.png.
export async function getStaticPaths() {
  const docs = await getCollection("docs");
  const notes = await getCollection("notes");
  const specimens = await getCollection("specimens");
  return [
    { params: { slug: "default" }, props: { title: site.tagline } },
    ...docs.map((d) => ({
      params: { slug: `docs/${d.id}` },
      props: { title: d.data.title, kicker: "Docs" },
    })),
    ...notes.map((n) => ({
      params: { slug: `notes/${n.id}` },
      props: { title: n.data.title, kicker: "Field notes" },
    })),
    ...specimens.map((s) => ({
      params: { slug: `library/${s.id}` },
      props: { title: `“${s.data.seed}” by ${s.data.by}`, kicker: "Library" },
    })),
  ];
}

export const GET: APIRoute = async ({ props }) => {
  const { title, kicker } = props as { title: string; kicker?: string };
  return new Response(new Uint8Array(await ogImage({ title, kicker })), {
    headers: { "Content-Type": "image/png" },
  });
};
