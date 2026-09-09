import * as stylex from "@stylexjs/stylex";
import { Icon, Text, VisuallyHidden } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { layer } from "@biotic/design/tokens/layer.stylex";
import { border, radius, shadow } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { useCallback, useEffect, useRef, useState } from "react";

interface Result {
  url: string;
  meta: { title?: string };
  excerpt: string;
}
interface Pagefind {
  init: () => Promise<void>;
  search: (q: string) => Promise<{ results: { data: () => Promise<Result> }[] }>;
}

const styles = stylex.create({
  bar: { gap: space.xs, alignItems: "center", display: "flex", paddingInlineEnd: space.xs },
  trigger: {
    padding: space.xs,
    borderColor: "transparent",
    borderRadius: radius.full,
    borderStyle: "solid",
    borderWidth: border.hairline,
    outline: "none",
    alignItems: "center",
    backgroundColor: { default: "transparent", ":hover": color.surfaceSunken },
    boxShadow: { default: "none", ":focus-visible": shadow.focus },
    color: color.inkSecondary,
    cursor: "pointer",
    display: "inline-flex",
    fontSize: "1.1rem",
    justifyContent: "center",
  },
  dialog: {
    padding: 0,
    borderColor: color.edgeSubtle,
    borderRadius: radius.lg,
    borderStyle: "solid",
    borderWidth: border.hairline,
    backgroundColor: color.surfaceRaised,
    boxShadow: shadow.lg,
    color: color.inkPrimary,
    zIndex: layer.overlay,
    marginTop: "10vh",
    maxWidth: "36rem",
    width: "min(36rem, 92vw)",
  },
  input: {
    padding: space.md,
    borderInlineWidth: 0,
    outline: "none",
    backgroundColor: "transparent",
    fontSize: "1.1rem",
    borderBottomColor: color.edgeSubtle,
    borderBottomStyle: "solid",
    borderBottomWidth: border.hairline,
    borderTopWidth: 0,
    width: "100%",
  },
  list: { margin: 0, padding: space.xs, listStyle: "none", maxHeight: "50vh", overflowY: "auto" },
  item: {
    padding: space.sm,
    borderRadius: radius.md,
    backgroundColor: {
      default: "transparent",
      ":focus-within": color.surfaceSunken,
      ":hover": color.surfaceSunken,
    },
    display: "block",
    textDecorationLine: "none",
  },
  title: { color: color.inkPrimary, fontWeight: 600 },
  excerpt: { color: color.inkSecondary, fontSize: "0.875rem" },
  empty: { padding: space.md, fontFamily: font.text },
});

/** Site search over the static Pagefind index; loads nothing until opened. */
export function Search({ base }: { base: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const engine = useRef<Pagefind | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[] | null>(null);
  const [failed, setFailed] = useState(false);

  const open = useCallback(() => dialog.current?.showModal(), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        (e.key === "k" && (e.metaKey || e.ctrlKey)) ||
        (e.key === "/" && !(e.target instanceof HTMLInputElement))
      ) {
        e.preventDefault();
        open();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const runSearch = async (q: string) => {
    setQuery(q);
    if (!q) {
      setResults(null);
      return;
    }
    try {
      if (!engine.current) {
        const mod = (await import(/* @vite-ignore */ `${base}pagefind/pagefind.js`)) as Pagefind;
        await mod.init();
        engine.current = mod;
      }
      const res = await engine.current.search(q);
      const data = await Promise.all(res.results.slice(0, 8).map((r) => r.data()));
      setResults(data);
    } catch {
      setFailed(true);
    }
  };

  return (
    <>
      <button type="button" onClick={open} title="Search (⌘K)" {...stylex.props(styles.trigger)}>
        <Icon name="search" />
        <VisuallyHidden>Search</VisuallyHidden>
      </button>
      <dialog ref={dialog} aria-label="Search" {...stylex.props(styles.dialog)}>
        <div {...stylex.props(styles.bar)}>
          <input
            type="search"
            placeholder="Search the docs"
            aria-label="Search query"
            autoComplete="off"
            value={query}
            onChange={(e) => void runSearch(e.target.value)}
            {...stylex.props(styles.input)}
          />
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            aria-label="Close search"
            {...stylex.props(styles.trigger)}
          >
            <Icon name="close" />
          </button>
        </div>
        {failed && (
          <Text tone="muted" style={styles.empty}>
            Search works on the published site; the index is built with it.
          </Text>
        )}
        {results?.length === 0 && !failed && (
          <Text tone="muted" style={styles.empty}>
            Nothing found.
          </Text>
        )}
        {results && results.length > 0 && (
          <ul {...stylex.props(styles.list)}>
            {results.map((r) => (
              <li key={r.url}>
                <a href={r.url} {...stylex.props(styles.item)}>
                  <div {...stylex.props(styles.title)}>{r.meta.title ?? r.url}</div>
                  <div
                    {...stylex.props(styles.excerpt)}
                    dangerouslySetInnerHTML={{ __html: r.excerpt }}
                  />
                </a>
              </li>
            ))}
          </ul>
        )}
      </dialog>
    </>
  );
}
