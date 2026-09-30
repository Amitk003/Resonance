import { useEffect } from "react";

/* Reveal cards when they scroll into view. One shot. */
export function useReveal(dep: unknown) {
  useEffect(() => {
    const nodes = Array.from(
      document.querySelectorAll(".card, .stats, .banner, .footer"),
    );
    nodes.forEach((n) => n.classList.add("reveal"));
    if (!("IntersectionObserver" in window)) {
      nodes.forEach((n) => n.classList.add("visible"));
      return;
    }
    const seen = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            seen.unobserve(e.target);
          }
        }
      },
      { threshold: 0.08 },
    );
    nodes.forEach((n) => seen.observe(n));
    return () => seen.disconnect();
  }, [dep]);
}
