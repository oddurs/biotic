import { site } from "../../site.config";

/** Prefixes a root-relative path with the deploy base so links work under a sub-path. */
export function href(path: string): string {
  const base = site.base.endsWith("/") ? site.base.slice(0, -1) : site.base;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}
