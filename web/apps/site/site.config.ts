// The one place the project's identity lives. Renaming the project is an edit here.
export const site = {
  name: "biotic",
  tagline: "An organism that grows its own body, from a seed.",
  description:
    "A culture of cells that write themselves, in a dish you can watch. A research instrument for open-ended evolution with semantic mutation.",
  repo: "https://github.com/oddurs/biotic",
  author: "Oddur Sigurdsson",
  // Where the site is served. The deploy workflow sets these for GitHub Pages.
  url: process.env.SITE_URL ?? "http://localhost:6969",
  base: process.env.SITE_BASE ?? "/",
  nav: [
    { label: "Docs", href: "/docs/" },
    { label: "Library", href: "/library/" },
    { label: "Research", href: "/research/" },
    { label: "Design", href: "/design/" },
  ],
} as const;
