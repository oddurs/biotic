import "../global.css";

// The StyleX plugin serves the collected CSS at this URL in dev, which is what the
// browser runner uses. With it present, axe can check real colour contrast.
const link = document.createElement("link");
link.rel = "stylesheet";
link.href = "/virtual:stylex.css";
document.head.append(link);
