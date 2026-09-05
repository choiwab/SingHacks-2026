import "@testing-library/jest-dom/vitest";

// jsdom implements neither scroll API; the shell scrolls its own main element.
Object.defineProperty(window, "scrollTo", {
  value: () => undefined,
  writable: true,
});
Object.defineProperty(Element.prototype, "scrollTo", {
  value: () => undefined,
  writable: true,
});
Object.defineProperty(Element.prototype, "scrollIntoView", {
  value: () => undefined,
  writable: true,
});

// Fluent's MessageBar reflow observes its own width; jsdom has no ResizeObserver.
window.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
