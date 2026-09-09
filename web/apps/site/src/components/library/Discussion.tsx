import { Link, Text } from "@biotic/design";
import { useEffect, useRef } from "react";

export interface GiscusConfig {
  repo: string;
  repoId: string;
  category: string;
  categoryId: string;
}

/** giscus threads, keyed by page path. Renders a plain link until the ids are configured. */
export function Discussion({ giscus, term }: { giscus: GiscusConfig; term: string }) {
  const host = useRef<HTMLDivElement>(null);
  const enabled = Boolean(giscus.repoId && giscus.categoryId);
  useEffect(() => {
    if (!enabled || !host.current || host.current.childElementCount) return;
    const s = document.createElement("script");
    s.src = "https://giscus.app/client.js";
    s.async = true;
    s.crossOrigin = "anonymous";
    const attrs: Record<string, string> = {
      "data-repo": giscus.repo,
      "data-repo-id": giscus.repoId,
      "data-category": giscus.category,
      "data-category-id": giscus.categoryId,
      "data-mapping": "specific",
      "data-term": term,
      "data-reactions-enabled": "1",
      "data-input-position": "top",
      "data-theme": "preferred_color_scheme",
      "data-lang": "en",
    };
    for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v);
    host.current.append(s);
  }, [enabled, giscus, term]);
  if (!enabled) {
    return (
      <Text tone="secondary">
        Discussion threads open once giscus is configured. Until then,{" "}
        <Link href={`https://github.com/${giscus.repo}/discussions`}>
          start a thread on GitHub Discussions
        </Link>
        .
      </Text>
    );
  }
  return <div ref={host} />;
}
