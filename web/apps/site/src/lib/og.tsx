import { Resvg } from "@resvg/resvg-js";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import satori from "satori";
import { site } from "../../site.config";

// Open Graph images, rendered at build from the same faces the site uses.
const require = createRequire(import.meta.url);
const font = (pkg: string, file: string) => readFile(require.resolve(`${pkg}/files/${file}`));

let fonts: Promise<{ name: string; data: Buffer; weight: 400 | 500 | 600 }[]> | undefined;
const loadFonts = () =>
  (fonts ??= Promise.all([
    font("@fontsource/fraunces", "fraunces-latin-500-normal.woff").then((data) => ({
      name: "Fraunces",
      data,
      weight: 500 as const,
    })),
    font("@fontsource/inter", "inter-latin-400-normal.woff").then((data) => ({
      name: "Inter",
      data,
      weight: 400 as const,
    })),
  ]));

export async function ogImage({
  title,
  kicker,
}: {
  title: string;
  kicker?: string;
}): Promise<Buffer> {
  const svg = await satori(
    <div
      style={{
        alignItems: "flex-start",
        backgroundColor: "#0f1712",
        color: "#eef4ef",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter",
        height: "100%",
        justifyContent: "space-between",
        padding: 72,
        width: "100%",
      }}
    >
      <div
        style={{
          color: "#5fc48a",
          display: "flex",
          fontSize: 28,
          letterSpacing: 2,
          textTransform: "uppercase",
        }}
      >
        {kicker ?? site.name}
      </div>
      <div
        style={{
          display: "flex",
          fontFamily: "Fraunces",
          fontSize: title.length > 40 ? 64 : 84,
          lineHeight: 1.1,
          maxWidth: 1000,
        }}
      >
        {title}
      </div>
      <div style={{ color: "#9fb3a6", display: "flex", fontSize: 28 }}>
        {site.name} · {site.tagline}
      </div>
    </div>,
    { width: 1200, height: 630, fonts: await loadFonts() },
  );
  return new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
}
